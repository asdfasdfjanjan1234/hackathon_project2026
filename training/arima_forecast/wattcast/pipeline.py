"""The training steps, shared by the numbered scripts and the notebook.

    pretrain   rank the ARIMA structures by how well they forecast Luzon's demand
    finetune   one ARIMA per AI agent on a device, each built on that agent's weekly routine and
               warm-started from the Luzon model; checked by forecasting held-out windows
    forecast   the electricity bill: baseline + AI cost so far this cycle + the time ahead,
               step by step and per agent, with ranges

The series are in steps of `step_minutes` (config.json; 15 minutes), so a device can be fine-tuned
on a few hours of readings. Durations in config.json are in hours and counted in steps here.

Both training steps save a checkpoint after every fit (checkpoint.py) and reuse matching ones, so an
interrupted run resumes where it stopped. Each saved model file carries a "run" record: the
configuration, package versions, timing, how many fits came from checkpoints, and any fit that
stopped at the iteration cap without converging.

There are no epochs in ARIMA training (see model.py). Every fit reports its optimizer iterations
instead, and with model.show_iterations on, its log-likelihood after each one.
"""

import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from . import backtest, bill, model, patterns, settings, steps
from .checkpoint import Checkpoints, fingerprint, slug
from .config import CONFIG, bill_settings, snapshot
from .features import PRIOR_WEIGHT

LUZON_SOURCE = "IEMOP RTD Luzon (CLUZ) demand"
MIN_HOURS = CONFIG["device"]["min_hours"]  # known hours a device needs before fine-tuning
MIN_DAYS = CONFIG["device"]["min_days"]
MAX_HOURS = CONFIG["forecast"]["max_hours"]
MIN_SEASONS = 2  # seasons a structure with a season needs to fit on, before the first held-out window
FIT_ERRORS = (np.linalg.LinAlgError, ValueError, FloatingPointError)
METHOD = 4  # raise when the model or backtest changes, so older checkpoints are refitted


def _line(m):
    return f"MASE {m['mase']}  WAPE {m['wape']}  window total off by {m['window_total_error']}"


def fit_note(trained):
    """How a fit's optimization ended, for the log: its iterations, or that it hit the cap."""
    if trained.get("iterations") is None:
        return ""
    if trained.get("converged", True):
        return f"  [{trained['iterations']} iterations]"
    return f"  [NOT converged: stopped at {trained['iterations']} of {trained.get('max_iterations')} iterations]"


def _watch(log, label):
    """A callback printing each iteration's log-likelihood when model.show_iterations is on, else None."""
    if not CONFIG["model"]["show_iterations"]:
        return None
    log(f"      fitting {label}")
    return lambda number, loglike: log(f"        iteration {number:>3}  log-likelihood {loglike:.3f}")


def _not_converged(entries):
    return [name for name, trained in entries if trained.get("converged") is False]


def luzon_checkpoints(fresh=False):
    return Checkpoints(settings.LUZON_CHECKPOINTS, CONFIG["checkpoints"], fresh)


def device_checkpoints(device_id, fresh=False):
    return Checkpoints(settings.device_checkpoints(device_id), CONFIG["checkpoints"], fresh)


def _windows(y, group, folds, horizon_hours=None, min_train_hours=None):
    """(origins, steps in a window) of the held-out windows of `y`, from the settings of `group`
    ("luzon" or "device") in config.json unless given."""
    horizon_hours = horizon_hours or CONFIG[group]["horizon_hours"]
    min_train_hours = CONFIG[group]["min_train_hours"] if min_train_hours is None else min_train_hours
    horizon = steps.count(horizon_hours, y.index)
    origins = backtest.usable_origins(y, folds, horizon, steps.count(min_train_hours, y.index))
    if not origins:
        raise ValueError(f"Not enough readings to hold out {horizon_hours:g} hours after {min_train_hours:g} hours "
                         f"to fit on ({group}.horizon_hours and {group}.min_train_hours in config.json)")
    return origins, horizon


def _fits(spec, train):
    """Whether `train` steps before the first held-out window are enough for `spec`: a structure
    with a season can't learn it from less than MIN_SEASONS of them."""
    return train >= MIN_SEASONS * spec.season


def _key(y, spec, start, **extra):
    """What a fit depends on: the data, the structure, where the optimizer starts, and the settings."""
    return fingerprint(y, spec=spec.label, start=start, maxiter=model.MAXITER, prior=PRIOR_WEIGHT,
                       method=METHOD, **extra)


def _evaluate(ckpt, name, y, spec, origins, start=None, source="", log=print, horizon=None):
    """backtest.evaluate, saved to and loaded from the checkpoint `name`. A fit that fails is
    checkpointed too, so a resumed run doesn't spend time failing again."""
    horizon = horizon or steps.per_day(y.index)
    key = _key(y, spec, start, origins=origins, horizon=horizon)
    hit = ckpt.load(name, key)
    if hit:
        if hit.get("failed"):
            raise ValueError(hit["failed"])
        forecasts = {int(p): pd.Series(v, index=y.index[int(p):int(p) + len(v)]) for p, v in hit["forecasts"].items()}
        return {"model": model.Model.from_dict(hit["model"]), "forecasts": forecasts, "metrics": hit["metrics"],
                "from_checkpoint": True}
    try:
        r = backtest.evaluate(y, spec, origins, horizon=horizon, start=start, source=source,
                              on_iteration=_watch(log, f"{spec.label} for the backtest"))
    except FIT_ERRORS as e:
        ckpt.save(name, key, {"spec": spec.label, "failed": f"{type(e).__name__}: {e}"})
        raise
    ckpt.save(name, key, {"spec": spec.label, "source": source, "metrics": r["metrics"],
                          "model": r["model"].to_dict(),
                          "forecasts": {str(p): f.round(6).tolist() for p, f in r["forecasts"].items()}})
    return {**r, "from_checkpoint": False}


def _fit_final(ckpt, name, y, spec, start=None, source="", log=print):
    """model.fit on all of `y`, saved to and loaded from the checkpoint `name`."""
    key = _key(y, spec, start, final=True)
    hit = ckpt.load(name, key)
    if hit:
        return model.Model.from_dict(hit["model"])
    final = model.fit(y, spec, start=start, source=source, on_iteration=_watch(log, f"{spec.label} on all the data"))
    ckpt.save(name, key, {"spec": spec.label, "source": source, "model": final.to_dict()})
    return final


def _run_record(ckpt, started, **extra):
    return {"started": datetime.fromtimestamp(started).isoformat(timespec="seconds"),
            "finished": datetime.now().isoformat(timespec="seconds"),
            "seconds": round(time.time() - started, 1), "checkpoints": ckpt.summary(), **snapshot(**extra)}


def _note(result):
    return "  (from checkpoint)" if result.get("from_checkpoint") else ""


def pretrain(y, specs=model.CANDIDATES, folds=CONFIG["luzon"]["folds"], ckpt=None, log=print,
             horizon_hours=None, min_train_hours=None):
    """Backtest every spec on Luzon's demand and keep each one's coefficients, best first.
    The best is refitted on all of `y`. Returns the dict saved as luzon_pretrained.json.
    horizon_hours, min_train_hours: the held-out windows, from the luzon settings unless given."""
    started = time.time()
    origins, horizon = _windows(y, "luzon", folds, horizon_hours, min_train_hours)
    ckpt = ckpt or luzon_checkpoints()
    ckpt.save_config(snapshot(step="pretrain", data=_data(y)))
    ranking = []
    for spec in specs:
        if not _fits(spec, origins[0]):
            log(f"  {spec.label:<24} skipped: needs {MIN_SEASONS} of its seasons before the held-out windows")
            continue
        try:
            r = _evaluate(ckpt, slug("backtest", spec.label), y, spec, origins, source=LUZON_SOURCE, log=log,
                          horizon=horizon)
        except FIT_ERRORS as e:
            log(f"  {spec.label:<24} could not be fitted ({type(e).__name__})")
            continue
        trained = r["model"].trained
        ranking.append({"spec": spec.label, "order": spec.order, "seasonal_order": spec.seasonal_order,
                        "aic": trained["aic"], "iterations": trained.get("iterations"),
                        "converged": trained.get("converged"), "metrics": r["metrics"], "params": r["model"].params})
        log(f"  {spec.label:<24} {_line(r['metrics'])}{fit_note(trained)}{_note(r)}")
    if not ranking:
        raise ValueError("None of the candidate structures could be fitted to the Luzon data")
    ranking.sort(key=lambda r: (r["metrics"]["mase"], r["aic"]))
    scale = backtest.scale(y, origins[0])
    baselines = {name: backtest.score(y, f, scale) for name, f in backtest.baselines(y, origins, horizon).items()}
    best = model.Spec(tuple(ranking[0]["order"]), tuple(ranking[0]["seasonal_order"]))
    final = _fit_final(ckpt, slug("final", best.label), y, best, source=LUZON_SOURCE, log=log)
    ranking[0]["params"] = final.params
    log(f"Best on Luzon: {best.label}, fitted on all the data{fit_note(final.trained)}")
    stuck = _not_converged([(f"{r['spec']} (backtest)", r) for r in ranking]
                           + [(f"{best.label} (final)", final.trained)])
    return {"created": datetime.now().isoformat(timespec="seconds"), "step_minutes": steps.minutes(y.index),
            "model": final.to_dict(), "ranking": ranking, "baselines": baselines, "folds": len(origins),
            "horizon_hours": steps.hours(horizon, y.index),
            "run": _run_record(ckpt, started, step="pretrain", data=_data(y), not_converged=stuck)}


def _data(y):
    return {"start": str(y.index[0]), "end": str(y.index[-1]), "step_minutes": steps.minutes(y.index),
            "hours": steps.hours(len(y), y.index), "known_hours": steps.hours(int(y.notna().sum()), y.index)}


def load_luzon():
    """[(structure, its Luzon coefficients)], best first; coefficients are None before pre-training.
    A Luzon model pre-trained at another step than config.json's is an error: its coefficients
    describe that step."""
    try:
        with open(settings.LUZON_MODEL) as f:
            luzon = json.load(f)
    except FileNotFoundError:
        return [(spec, None) for spec in model.CANDIDATES]
    if luzon.get("step_minutes", 60) != steps.MINUTES:
        raise ValueError(f"The Luzon model was pre-trained at {luzon.get('step_minutes', 60)}-minute steps and "
                         f"config.json says {steps.MINUTES}: run 04_pretrain_luzon.py again")
    return [(model.Spec(tuple(r["order"]), tuple(r["seasonal_order"])), r["params"]) for r in luzon["ranking"]]


def check_enough(y):
    """Raise with a clear message if a device doesn't have enough readings to fine-tune."""
    known = steps.hours(int(y.notna().sum()), y.index)
    days = len(set(y.index[y.notna()].date))
    if known < MIN_HOURS or days < MIN_DAYS:
        raise ValueError(f"{known:g} known hours on {days} days; fine-tuning needs {MIN_HOURS:g} hours "
                         f"on {MIN_DAYS}+ days. Keep the device reader running, then export again.")
    return known, days


def _finetune_agent(ckpt, name, y, origins, luzon, top, source, log, horizon=None):
    """Every candidate for one agent's series, best first by held-out error, with its forecasts:
    the routine alone, and the `top` best Luzon structures the series is long enough for."""
    candidates = [(model.ROUTINE_ONLY, "cold", None)]
    for spec, params in [(s, p) for s, p in luzon if _fits(s, origins[0])][:top]:
        candidates += [(spec, "warm", params)] if params else []
        candidates.append((spec, "cold", None))
    tried = []
    for spec, start_name, start in candidates:
        try:
            r = _evaluate(ckpt, slug("backtest", name, spec.label, start_name), y, spec, origins, start, source, log,
                          horizon)
        except FIT_ERRORS as e:
            log(f"    {spec.label:<24} {start_name}  could not be fitted ({type(e).__name__})")
            continue
        trained = r["model"].trained
        tried.append({"spec": spec.label, "order": spec.order, "seasonal_order": spec.seasonal_order,
                      "start": start_name, "aic": trained["aic"], "iterations": trained.get("iterations"),
                      "converged": trained.get("converged"), "metrics": r["metrics"],
                      "forecasts": r["forecasts"], "start_params": start})
        log(f"    {spec.label:<24} {start_name}  {_line(r['metrics'])}{fit_note(trained)}{_note(r)}")
    if not tried:
        raise ValueError(f"No model could be fitted to {source}")
    # Best first. With allow_routine_only off, the routine alone is listed last (it's there to compare
    # against) unless no ARIMA could be fitted at all.
    demote = not CONFIG["device"]["allow_routine_only"]
    return sorted(tried, key=lambda t: (demote and t["spec"] == model.ROUTINE_ONLY.label, t["metrics"]["mae"], t["aic"]))


def finetune(agents, device_id, luzon, folds=CONFIG["device"]["folds"], top=CONFIG["device"]["top_structures"],
             ckpt=None, bill_cfg=None, log=print, horizon_hours=None, min_train_hours=None):
    """Fine-tune one model per AI agent (a column of readings.agent_series).

    For each agent: the routine alone, and each of the `top` Luzon structures started from the Luzon
    coefficients (warm) and from scratch (cold). The one with the lowest held-out error is refitted
    on all the agent's steps. The agents' held-out forecasts are then added up and scored against
    the baselines on the device's total AI energy: that's the check that matters for the bill.
    bill_cfg: the backend's Config, to record the bill settings with the run.
    horizon_hours, min_train_hours: the held-out windows, from the device settings unless given.
    Returns the dict saved as device_<id>_model.json.
    """
    started = time.time()
    total = agents.sum(axis=1, min_count=1)
    known, days = check_enough(total)
    origins, horizon = _windows(total, "device", folds, horizon_hours, min_train_hours)
    log(f"  held out: the last {len(origins)} window{'s' * (len(origins) > 1)} of "
        f"{steps.hours(horizon, total.index):g} hours, fitted on the {steps.hours(origins[0], total.index):g} hours before")
    ckpt = ckpt or device_checkpoints(device_id)
    extra = {"step": "finetune", "device_id": device_id, "data": _data(total), "agents": list(agents.columns),
             "bill_settings": bill_settings(bill_cfg) if bill_cfg else None}
    ckpt.save_config(snapshot(**extra))
    out, summed, stuck = {}, {p: 0.0 for p in origins}, []
    for name in agents.columns:
        y = agents[name]
        source = f"device {device_id}, {name}"
        log(f"  {name}")
        tried = _finetune_agent(ckpt, name, y, origins, luzon, top, source, log, horizon)
        best = tried[0]
        spec = model.Spec(tuple(best["order"]), tuple(best["seasonal_order"]))
        final = _fit_final(ckpt, slug("final", name, spec.label, best["start"]), y, spec, best["start_params"],
                           source, log)
        for p in origins:
            summed[p] = summed[p] + best["forecasts"][p]
        log(f"    chosen: {best['spec']} ({best['start']} start), fitted on all the data{fit_note(final.trained)}")
        stuck += _not_converged([(f"{name}: {t['spec']} {t['start']} (backtest)", t) for t in tried]
                                + [(f"{name}: {best['spec']} {best['start']} (final)", final.trained)])
        out[name] = {"model": final.to_dict(), "chosen": {"spec": best["spec"], "start": best["start"]},
                     "share_of_energy": round(float(y.sum() / total.sum()), 4) if total.sum() else None,
                     "tried": [{k: v for k, v in t.items() if k not in ("forecasts", "start_params")} for t in tried]}
    scale = backtest.scale(total, origins[0])
    metrics = {"arima_by_agent": backtest.score(total, summed, scale)}
    metrics.update({name: backtest.score(total, f, scale)
                    for name, f in backtest.baselines(total, origins, horizon).items()})
    ours = metrics["arima_by_agent"]["mae"]
    beats = all(ours < m["mae"] for name, m in metrics.items() if name != "arima_by_agent")
    for name, m in metrics.items():
        log(f"  total, {name:<15} {_line(m)}")
    return {"created": datetime.now().isoformat(timespec="seconds"), "device_id": device_id,
            "step_minutes": steps.minutes(total.index), "agents": out,
            "total": metrics, "beats_baselines": beats, "folds": len(origins),
            "horizon_hours": steps.hours(horizon, total.index),
            # How much of the day has been seen: the rest is forecast at the device's average level.
            "coverage": {"known_hours": known, "days": days,
                         "hours_of_day": int(total.dropna().index.hour.nunique())},
            "thresholds_w": patterns.thresholds(patterns.watts(total)),
            "run": _run_record(ckpt, started, not_converged=stuck, **extra)}


def forecast(saved, agents, energy, cfg, hours=None, paths=CONFIG["forecast"]["paths"], now=None):
    """The bill forecast from the current step to the end of the billing cycle (or `hours` ahead).

    energy: the device's readings by step (readings.ai_energy), for the AI cost measured so far.
    Returns (table, summary): per step, each agent's kWh and the total kWh and pesos with their
    range and usage level; the summary has totals for the next day, week and rest of the cycle, the
    cost per agent, and the projected bill (baseline + AI so far + AI still to come).
    Steps between the last reading and now are unknown, and bridged by the models.
    """
    step, per_hour = steps.step_of(agents.index), steps.per_hour(agents.index)
    if saved.get("step_minutes", 60) != steps.minutes(agents.index):
        raise ValueError(f"The model was fine-tuned at {saved.get('step_minutes', 60)}-minute steps and the "
                         f"readings are in {steps.minutes(agents.index)}-minute steps: run 05_finetune_device.py again")
    now = (now or pd.Timestamp.now(tz=settings.TZ).tz_localize(None)).floor(step)
    if agents.index[-1] < now - step:
        agents = agents.reindex(pd.date_range(agents.index[0], now - step, freq=step))
    t = bill.tariff(cfg)
    cycle_start, cycle_end = bill.billing_cycle(now.date(), t["cycle_start_day"])
    first = agents.index[-1] + step
    if hours is None:
        count = int((pd.Timestamp(cycle_end) + pd.Timedelta(days=1) - first) / step)
    else:
        count = hours * per_hour
    count = max(1, min(count, MAX_HOURS * per_hour))

    index = pd.date_range(first, periods=count, freq=step)
    total_paths = np.zeros((count, paths))
    by_agent = {}
    for seed, name in enumerate(agents.columns):
        m = model.Model.from_dict(saved["agents"][name]["model"])
        sims = m.simulate(agents[name], count, paths=paths, seed=seed)
        total_paths += sims
        by_agent[name] = np.median(sims, axis=1)
    table = bill.forecast_table(total_paths, index, t, saved["thresholds_w"], by_agent)
    # Totals are at least as uncertain as the totals of the held-out windows were wrong.
    error = saved["total"]["arima_by_agent"]["window_total_error"] or 0.0
    totals = bill.totals(total_paths, index, t, today=now.date(), rel_error=error)
    rate = bill.rates(index, t).to_numpy()
    in_cycle = index.date <= cycle_end
    agent_costs = {name: round(float((wh / 1000 * rate)[in_cycle].sum()), 2) for name, wh in by_agent.items()}
    summary = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "device_id": saved["device_id"], "step_minutes": steps.minutes(index),
        "from": str(index[0]), "to": str(index[-1]), "tariff": t,
        "totals": totals, "cost_by_agent_rest_of_cycle": agent_costs,
        "bill": bill.projected_bill(energy, total_paths, index, t, cfg.BASELINE_BILL, cycle_start, cycle_end, now,
                                    rel_error=error),
        "backtest_total_error": error, "backtest_horizon_hours": saved.get("horizon_hours"),
        "coverage": saved.get("coverage"),
        "hours_by_level": {level: steps.hours(n, index) for level, n in table["level"].value_counts().items()},
        "models": {name: a["chosen"] for name, a in saved["agents"].items()},
        "beats_baselines": saved["beats_baselines"],
        "model_trained": saved["created"], "bill_settings": bill_settings(cfg),
    }
    return table, summary
