"""The bill forecast from this device's fine-tuned ARIMA models, when there are any and they've
earned it.

The training pipeline (training/arima_forecast) saves one file per device, device_<id>_model.json:
an ARIMA per AI agent fitted on the device's 15-minute readings, with a backtest against simple
baselines (repeat the last value, the same time a day earlier, ...). arima_ahead() runs those
models over the latest readings and simulates the rest of the billing cycle with
wattcast.pipeline.forecast; nothing is refitted. forecasting.forecast_bill then takes the days
ahead from it in place of its trend.

ARIMA_FORECAST (.env) picks when: "auto" only when the model beat the baselines in its backtest,
"on" whenever there is one, "off" never. When it isn't used (no model file, the training packages
not installed, no readings) the trend forecast is, and the returned `method` says why.
"""

import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import date
from types import SimpleNamespace

log = logging.getLogger(__name__)

# The training package (wattcast), which runs the models.
TRAINING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                            "training", "arima_forecast")

MODES = ("auto", "on", "off")  # ARIMA_FORECAST; anything else is "auto"

# (model file, its mtime, mode, bill settings, 5-minute slot) -> (ahead, method). The dashboard asks for
# the forecast often, and it only moves on as readings come in or the model is retrained.
_cache = {}
CACHE_SIZE = 8
REFRESH_S = 300  # how long a forecast is reused; the model takes a second or two to run


def model_path(cfg, device_id):
    return os.path.join(cfg["ARIMA_MODEL_DIR"], f"device_{device_id}_model.json")


def _trend(reason, **extra):
    return None, {"name": "trend", "reason": reason, **extra}


def _wattcast():
    """(pipeline, readings) from the training package. Raises ImportError when it or the packages it
    needs (pandas, statsmodels) aren't installed."""
    if TRAINING_DIR not in sys.path:
        sys.path.append(TRAINING_DIR)
    from wattcast import pipeline, readings

    return pipeline, readings


def _bill_cfg(params):
    """The bill settings wattcast reads, from this request's (the user's) settings."""
    return SimpleNamespace(ELECTRICITY_RATE=params["rate"], TARIFF=params["tariff"],
                           POP_PEAK_RATE=params["peak_rate"], POP_OFFPEAK_RATE=params["offpeak_rate"],
                           BILLING_CYCLE_START_DAY=params["cycle_start_day"], BASELINE_BILL=params["baseline_bill"])


def _agents(readings, energy, by_app, names):
    """The readings by agent in the columns the model has. Agents that appeared after it was
    fine-tuned are forecast with "Other AI apps" when it has that model."""
    agents = readings.agent_series(energy, by_app)
    none = energy["wh"] * 0  # 0, and still unknown (NaN) where the reader didn't run
    for name in names:
        if name not in agents:
            agents[name] = none
    extra = [c for c in agents.columns if c not in names]
    if extra and readings.OTHER in names:
        agents[readings.OTHER] = agents[readings.OTHER] + agents[extra].sum(axis=1)
    return agents[names]


def arima_ahead(conn, device_id, params, cfg):
    """(ahead, method).

    ahead: {"days": {date: AI kWh still to come that day, from now}, "low", "high": the range of
    their total as a share of it (the model's 80% interval)}, or None: use the trend.
    method: which forecast the bill is on and why, with the ARIMA model's details when there is one.
    """
    mode = cfg["ARIMA_FORECAST"] if cfg["ARIMA_FORECAST"] in MODES else "auto"
    if mode == "off":
        return _trend("ARIMA is turned off (ARIMA_FORECAST=off)")
    if device_id is None:
        return _trend("No readings from this device yet")
    path = model_path(cfg, device_id)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return _trend("No fine-tuned ARIMA model for this device yet")

    key = (path, mtime, mode, tuple(sorted(params.items())), time.time() // REFRESH_S)
    if key in _cache:
        return _cache[key]

    with open(path) as f:
        saved = json.load(f)
    about = {"device_id": device_id, "trained": saved.get("created"),
             "beats_baselines": bool(saved.get("beats_baselines")),
             "models": {name: a["chosen"]["spec"] for name, a in saved.get("agents", {}).items()},
             "coverage": saved.get("coverage")}
    if mode == "auto" and not about["beats_baselines"]:
        return _remember(key, _trend("The fine-tuned ARIMA didn't beat simple baselines in its backtest", arima=about))
    try:
        pipeline, readings = _wattcast()
    except (ImportError, OSError) as e:
        return _trend(f"Can't load the ARIMA code ({e}): pip install -r backend/requirements.txt", arima=about)

    try:
        energy, by_app = readings.ai_energy(conn, device_id)
        if energy.empty:
            return _remember(key, _trend("No readings from this device yet", arima=about))
        agents = _agents(readings, energy, by_app, list(saved["agents"]))
        table, summary = pipeline.forecast(saved, agents, energy, _bill_cfg(params))
    except Exception as e:  # a failed forecast falls back to the trend instead of failing the dashboard
        log.exception("ARIMA forecast for device %s failed", device_id)
        return _trend(f"The ARIMA forecast failed: {e}", arima=about)

    bill = summary["bill"]
    in_cycle = table[table.index.date <= date.fromisoformat(bill["cycle"]["end"])]
    # Steps' medians don't add up to the median of the total; scale them to it, so the days ahead
    # add up to the bill wattcast projects (its range is of that total).
    cost = float(in_cycle["cost"].sum())
    scale = bill["ai_cost_remaining"] / cost if cost > 0 else 1.0
    days = defaultdict(float)
    for when, kwh in in_cycle["kwh"].items():
        days[when.date()] += float(kwh) * scale
    rest = bill["ai_cost_remaining"]
    ahead = {"days": dict(days),
             "low": bill["ai_cost_remaining_low"] / rest if rest > 0 else 1.0,
             "high": bill["ai_cost_remaining_high"] / rest if rest > 0 else 1.0}
    reason = ("The fine-tuned ARIMA beat simple baselines in its backtest" if about["beats_baselines"] else
              "ARIMA_FORECAST=on: the fine-tuned ARIMA, though it didn't beat simple baselines in its backtest")
    return _remember(key, (ahead, {"name": "arima", "reason": reason, "arima": about,
                                   "interval": pipeline.bill.INTERVAL}))


def _remember(key, result):
    if len(_cache) >= CACHE_SIZE:
        _cache.clear()
    _cache[key] = result
    return result


_accuracy_cache = {}


def accuracy(device_id):
    """The fine-tuned models scored as an "in use / idle" classifier on their held-out windows
    (accuracy, precision, recall, F1; wattcast/classify.py), at a few "in use" thresholds, next to
    simple baselines. {"available": False, "reason"} when there is nothing to score yet."""
    if device_id is None:
        return {"available": False, "reason": "No readings from this device yet"}
    try:
        _wattcast()
        from wattcast import classify, settings
    except (ImportError, OSError) as e:
        return {"available": False, "reason": f"Can't load the ARIMA code ({e}): pip install -r backend/requirements.txt"}

    # Re-scored when fine-tuning or an export changes these files.
    files = [os.path.join(settings.device_checkpoints(device_id), "config.json"),
             settings.device_artifact(device_id, "model.json"),
             settings.device_data(device_id, "energy.csv"), settings.device_data(device_id, "by_app.csv")]
    key = (device_id, tuple(os.path.getmtime(f) if os.path.exists(f) else None for f in files))
    if key not in _accuracy_cache:
        try:
            result = {"available": True, **classify.report(device_id)}
        except (FileNotFoundError, ValueError) as e:
            result = {"available": False, "reason": str(e)}
        except Exception as e:  # a failed score shows as a note instead of failing the dashboard
            log.exception("Scoring the ARIMA models of device %s failed", device_id)
            result = {"available": False, "reason": f"Scoring failed: {e}"}
        _accuracy_cache.clear()
        _accuracy_cache[key] = result
    return _accuracy_cache[key]
