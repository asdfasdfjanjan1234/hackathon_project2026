"""A device's fine-tuned models scored as an "in use / idle" classifier: accuracy, precision, recall, F1.

The models forecast Wh per step, so these scores need a yes/no question first: is the agent in use
in this step? A step is "in use" when its energy, as Wh per hour, is at least agents.used_wh in
config.json (0.05 Wh per hour = 0.0125 Wh per 15-minute step), the rule readings.agent_series uses to
decide whether an agent gets its own model. The forecast and the actual reading of every held-out
step are each turned into in use / idle, and compared:

    accuracy    share of held-out steps called right
    precision   of the steps forecast "in use", the share that were (None when none were forecast)
    recall      of the steps that were in use, the share forecast "in use"
    f1          the harmonic mean of precision and recall

"Always idle" is scored too: on a mostly idle device it reaches a high accuracy by never saying "in
use", so accuracy means something only next to it. F1 is the score to look at.

Nothing is fitted. The held-out forecasts come from the device's backtest checkpoints (checkpoint.py),
the actual readings from data/processed, and the baselines from backtest.py on the same windows.
"""

import glob
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from . import backtest, readings, settings, steps
from .config import CONFIG

USED_WH = CONFIG["agents"]["used_wh"]  # Wh per hour
SWEEP_WH = (0.005, 0.01, 0.02, 0.05, 0.1)
ALWAYS_IDLE = "Always idle"


def scores(actual, predicted):
    """Accuracy, precision, recall and F1 of two boolean arrays, with None where undefined (0/0)."""
    tp = int(np.sum(actual & predicted))
    fp = int(np.sum(~actual & predicted))
    fn = int(np.sum(actual & ~predicted))
    tn = int(np.sum(~actual & ~predicted))
    return from_counts(tp, fp, fn, tn)


def from_counts(tp, fp, fn, tn):
    n = tp + fp + fn + tn
    return {"accuracy": (tp + tn) / n if n else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            # nothing in use and nothing forecast in use: no positives to score
            "f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "steps": n}


def pooled(score_list):
    """One score over several agents' held-out steps, from their counts."""
    return from_counts(*(sum(s[k] for s in score_list) for k in ("tp", "fp", "fn", "tn")))


def held_out(y, forecasts):
    """(actual, forecast) Wh of the measured held-out steps, from {origin: forecast series}."""
    actual, forecast = [], []
    for f in forecasts.values():
        a = y.reindex(f.index)
        seen = a.notna()
        actual.append(a[seen].to_numpy())
        forecast.append(f[seen].to_numpy())
    return np.concatenate(actual), np.concatenate(forecast)


def _run(device_id):
    folder = settings.device_checkpoints(device_id)
    try:
        with open(os.path.join(folder, "config.json")) as f:
            return folder, json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"No checkpoints in {folder}: run 05_finetune_device.py first.") from None


def load_checkpoints(device_id, agents):
    """[{agent, spec, start, forecasts: {origin: series}, horizon}] of every backtest checkpoint of the
    device. Raises ValueError when the readings have changed since they were fitted."""
    folder, run = _run(device_id)
    for name in run["agents"]:
        if name not in agents:
            raise ValueError(f"The checkpoints are for agent '{name}', which the readings don't have now. "
                             "Run 05_finetune_device.py again.")
    first = agents[run["agents"][0]].index
    if str(first[0]) != run["data"]["start"] or str(first[-1]) != run["data"]["end"]:
        raise ValueError(f"The checkpoints were fitted on {run['data']['start']} to {run['data']['end']}, the "
                         f"readings now run {first[0]} to {first[-1]}. Run 05_finetune_device.py again.")
    out = []
    for path in sorted(glob.glob(os.path.join(folder, "backtest__*.json"))):
        with open(path) as f:
            ck = json.load(f)
        agent = next((a for a in run["agents"] if ck["source"].endswith(a)), None)
        if agent is None or not ck.get("forecasts"):
            continue  # an agent from an older run, or a fit that failed
        index = agents[agent].index
        out.append({"agent": agent, "spec": ck["spec"], "start": os.path.basename(path)[:-5].rsplit("__", 1)[-1],
                    "horizon": max(len(v) for v in ck["forecasts"].values()),
                    "forecasts": {int(p): pd.Series(v, index=index[int(p):int(p) + len(v)])
                                  for p, v in ck["forecasts"].items()}})
    if not out:
        raise FileNotFoundError(f"No backtest checkpoints in {folder}: run 05_finetune_device.py first.")
    return out, run


def held_out_steps(device_id):
    """Every candidate's and baseline's held-out (actual, forecast) Wh, per agent, and the run record:
    ({agent: [{"model", "spec", "start", "kind", "actual", "forecast"}]}, run)."""
    energy = readings.load_energy(settings.device_data(device_id, "energy.csv"))
    agents = readings.agent_series(energy, readings.load_by_app(settings.device_data(device_id, "by_app.csv")))
    checkpoints, run = load_checkpoints(device_id, agents)
    out = {}
    for ck in checkpoints:
        y = agents[ck["agent"]]
        actual, forecast = held_out(y, ck["forecasts"])
        rows = out.setdefault(ck["agent"], [])
        if not rows:  # the yardsticks, once per agent, on the same held-out windows
            rows.append({"model": ALWAYS_IDLE, "kind": "baseline", "actual": actual, "forecast": np.zeros(len(actual))})
            for name, f in backtest.baselines(y, sorted(ck["forecasts"]), ck["horizon"]).items():
                a, b = held_out(y, f)
                rows.append({"model": name.replace("_", " ").capitalize(), "kind": "baseline", "actual": a, "forecast": b})
        rows.append({"model": f"{ck['spec']}, {ck['start']}", "spec": ck["spec"], "start": ck["start"],
                     "kind": "model", "actual": actual, "forecast": forecast})
    for agent, rows in out.items():  # candidates first, then the yardsticks
        out[agent] = [r for r in rows if r["kind"] == "model"] + [r for r in rows if r["kind"] == "baseline"]
    return out, run, energy


def score_rows(rows, used_wh, index):
    """Each row's scores with "in use" from `used_wh` Wh per hour."""
    per_step = used_wh / steps.per_hour(index)
    return [{**{k: v for k, v in r.items() if k not in ("actual", "forecast")},
             **scores(r["actual"] >= per_step, r["forecast"] >= per_step)} for r in rows]


def chosen(device_id):
    """{agent: (spec, start)} of the models fine-tuning picked, from device_<id>_model.json, or {}."""
    try:
        with open(settings.device_artifact(device_id, "model.json")) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return {}
    return {name: (a["chosen"]["spec"], a["chosen"]["start"]) for name, a in saved.get("agents", {}).items()}


def report(device_id, thresholds=SWEEP_WH, default=USED_WH):
    """Everything the dashboard shows, at each threshold in `thresholds` (and `default`):

    {"device_id", "data": {start, end, hours}, "fitted", "default_used_wh",
     "thresholds": [{"used_wh", "per_step_wh", "in_use_steps", "steps",
                     "chosen": pooled scores of the picked models,
                     "always_idle", "baselines": {name: pooled scores},
                     "agents": {agent: [row scores, with "chosen": bool]}}]}
    """
    per_agent, run, energy = held_out_steps(device_id)
    picked = chosen(device_id)
    out = []
    for used_wh in sorted({*thresholds, default}):
        agents, mine, yard = {}, [], {}
        for agent, rows in per_agent.items():
            scored = score_rows(rows, used_wh, energy.index)
            models = [r for r in scored if r["kind"] == "model"]
            best = next((r for r in models if (r["spec"], r["start"]) == picked.get(agent)), models[0])
            for r in scored:
                r["chosen"] = r is best
                if r["kind"] == "baseline":
                    yard.setdefault(r["model"], []).append(r)
            mine.append(best)
            agents[agent] = scored
        total = pooled(mine)
        out.append({"used_wh": used_wh, "per_step_wh": used_wh / steps.per_hour(energy.index),
                    "in_use_steps": total["tp"] + total["fn"], "steps": total["steps"],
                    "chosen": total, "always_idle": pooled(yard.pop(ALWAYS_IDLE)),
                    "baselines": {name: pooled(s) for name, s in yard.items()}, "agents": agents})
    fitted = os.path.getmtime(os.path.join(settings.device_checkpoints(device_id), "config.json"))
    return {"device_id": device_id, "data": run["data"], "fitted": datetime.fromtimestamp(fitted).isoformat(timespec="minutes"),
            "default_used_wh": default, "thresholds": out}
