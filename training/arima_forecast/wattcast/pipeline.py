"""The training steps, shared by the numbered scripts and the notebook.

    pretrain   pick the seasonal ARIMA structures that forecast Luzon's hourly demand best
    finetune   one ARIMA per AI agent on a device, each built on that agent's weekly routine and
               warm-started from the Luzon model; checked by forecasting held-out days
    forecast   the electricity bill: baseline + AI cost so far this cycle + the hours ahead,
               hour by hour and per agent, with ranges

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

from . import backtest, bill, model, patterns, settings
from .checkpoint import Checkpoints, fingerprint, slug
from .config import CONFIG, bill_settings, snapshot
from .features import PRIOR_WEIGHT

LUZON_SOURCE = "IEMOP RTD Luzon (CLUZ) demand"
MIN_HOURS = CONFIG["device"]["min_hours"]  # known hours a device needs before fine-tuning
MIN_DAYS = CONFIG["device"]["min_days"]
MAX_HOURS = CONFIG["forecast"]["max_hours"]
FIT_ERRORS = (np.linalg.LinAlgError, ValueError, FloatingPointError)
METHOD = 3  # raise when the model or backtest changes, so older checkpoints are refitted


def _line(m):
    return f"MASE {m['mase']}  WAPE {m['wape']}  day total off by {m['day_total_error']}"


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


def _key(y, spec, start, **extra):
    """What a fit depends on: the data, the structure, where the optimizer starts, and the settings."""
    return fingerprint(y, spec=spec.label, start=start, maxiter=model.MAXITER, prior=PRIOR_WEIGHT,
                       method=METHOD, **extra)


def _evaluate(ckpt, name, y, spec, origins, start=None, source="", log=print):
    """backtest.evaluate, saved to and loaded from the checkpoint `name`. A fit that fails is
    checkpointed too, so a resumed run doesn't spend time failing again."""
    key = _key(y, spec, start, origins=origins, horizon=backtest.HORIZON)
    hit = ckpt.load(name, key)
    if hit:
        if hit.get("failed"):
            raise ValueError(hit["failed"])
        forecasts = {int(p): pd.Series(v, index=y.index[int(p):int(p) + len(v)]) for p, v in hit["forecasts"].items()}
        return {"model": model.Model.from_dict(hit["model"]), "forecasts": forecasts, "metrics": hit["metrics"],
                "from_checkpoint": True}
    try:
        r = backtest.evaluate(y, spec, origins, start=start, source=source,
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
    final = model.fit(y, spec, start=start, source=source, on_iteration=_watch(log, f"{spec.label} on all hours"))
    ckpt.save(name, key, {"spec": spec.label, "source": source, "model": final.to_dict()})
    return final


def _run_record(ckpt, started, **extra):
    return {"started": datetime.fromtimestamp(started).isoformat(timespec="seconds"),
            "finished": datetime.now().isoformat(timespec="seconds"),
            "seconds": round(time.time() - started, 1), "checkpoints": ckpt.summary(), **snapshot(**extra)}


def _note(result):
    return "  (from checkpoint)" if result.get("from_checkpoint") else ""


def pretrain(y, specs=model.CANDIDATES, folds=CONFIG["luzon"]["folds"], ckpt=None, log=print):
    """Backtest every spec on Luzon hourly MWh and keep each one's coefficients, best first.
    The best is refitted on all of `y`. Returns the dict saved as luzon_pretrained.json."""
    started = time.time()
    ckpt = ckpt or luzon_checkpoints()
    ckpt.save_config(snapshot(step="pretrain", data=_data(y)))
    origins = backtest.usable_origins(y, folds)
    ranking = []
    for spec in specs:
        try:
            r = _evaluate(ckpt, slug("backtest", spec.label), y, spec, origins, source=LUZON_SOURCE, log=log)
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
    baselines = {name: backtest.score(y, f, scale) for name, f in backtest.baselines(y, origins).items()}
    best = model.Spec(tuple(ranking[0]["order"]), tuple(ranking[0]["seasonal_order"]))
    final = _fit_final(ckpt, slug("final", best.label), y, best, source=LUZON_SOURCE, log=log)
    ranking[0]["params"] = final.params
    log(f"Best on Luzon: {best.label}, fitted on all hours{fit_note(final.trained)}")
    stuck = _not_converged([(f"{r['spec']} (backtest)", r) for r in ranking]
                           + [(f"{best.label} (final)", final.trained)])
    return {"created": datetime.now().isoformat(timespec="seconds"), "model": final.to_dict(),
            "ranking": ranking, "baselines": baselines, "folds": len(origins),
            "run": _run_record(ckpt, started, step="pretrain", data=_data(y), not_converged=stuck)}


def _data(y):
    return {"start": str(y.index[0]), "end": str(y.index[-1]), "hours": int(len(y)),
            "known_hours": int(y.notna().sum())}


def load_luzon():
    """[(structure, its Luzon coefficients)], best first; coefficients are None before pre-training."""
    try:
        with open(settings.LUZON_MODEL) as f:
            luzon = json.load(f)
    except FileNotFoundError:
        return [(spec, None) for spec in model.CANDIDATES]
    return [(model.Spec(tuple(r["order"]), tuple(r["seasonal_order"])), r["params"]) for r in luzon["ranking"]]


def check_enough(y):
    """Raise with a clear message if a device doesn't have enough readings to fine-tune."""
    known = int(y.notna().sum())
    days = len(set(y.index[y.notna()].date))
    if known < MIN_HOURS or days < MIN_DAYS:
        raise ValueError(f"{known} known hours on {days} days; fine-tuning needs {MIN_HOURS} hours "
                         f"on {MIN_DAYS}+ days. Keep the device reader running, then export again.")
    return known, days


def _finetune_agent(ckpt, name, y, origins, luzon, top, source, log):
    """Every candidate for one agent's series, best first by held-out error, with its forecasts."""
    candidates = [(model.ROUTINE_ONLY, "cold", None)]
    for spec, params in luzon[:top]:
        candidates += [(spec, "warm", params)] if params else []
        candidates.append((spec, "cold", None))
    tried = []
    for spec, start_name, start in candidates:
        try:
            r = _evaluate(ckpt, slug("backtest", name, spec.label, start_name), y, spec, origins, start, source, log)
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
             ckpt=None, bill_cfg=None, log=print):
    """Fine-tune one model per AI agent (a column of readings.agent_series).

    For each agent: the routine alone, and each of the `top` Luzon structures started from the Luzon
    coefficients (warm) and from scratch (cold). The one with the lowest held-out error is refitted
    on all the agent's hours. The agents' held-out forecasts are then added up and scored against
    the baselines on the device's total AI energy: that's the check that matters for the bill.
    bill_cfg: the backend's Config, to record the bill settings with the run.
    Returns the dict saved as device_<id>_model.json.
    """
    started = time.time()
    total = agents.sum(axis=1, min_count=1)
    _, days = check_enough(total)
    origins = backtest.usable_origins(total, min(folds, days - 2))
    if not origins:
        raise ValueError("Not enough known hours to hold out a day: collect more readings")
    ckpt = ckpt or device_checkpoints(device_id)
    extra = {"step": "finetune", "device_id": device_id, "data": _data(total), "agents": list(agents.columns),
             "bill_settings": bill_settings(bill_cfg) if bill_cfg else None}
    ckpt.save_config(snapshot(**extra))
    out, summed, stuck = {}, {p: 0.0 for p in origins}, []
    for name in agents.columns:
        y = agents[name]
        source = f"device {device_id}, {name}"
        log(f"  {name}")
        tried = _finetune_agent(ckpt, name, y, origins, luzon, top, source, log)
        best = tried[0]
        spec = model.Spec(tuple(best["order"]), tuple(best["seasonal_order"]))
        final = _fit_final(ckpt, slug("final", name, spec.label, best["start"]), y, spec, best["start_params"],
                           source, log)
        for p in origins:
            summed[p] = summed[p] + best["forecasts"][p]
        log(f"    chosen: {best['spec']} ({best['start']} start), fitted on all hours{fit_note(final.trained)}")
        stuck += _not_converged([(f"{name}: {t['spec']} {t['start']} (backtest)", t) for t in tried]
                                + [(f"{name}: {best['spec']} {best['start']} (final)", final.trained)])
        out[name] = {"model": final.to_dict(), "chosen": {"spec": best["spec"], "start": best["start"]},
                     "share_of_energy": round(float(y.sum() / total.sum()), 4) if total.sum() else None,
                     "tried": [{k: v for k, v in t.items() if k not in ("forecasts", "start_params")} for t in tried]}
    scale = backtest.scale(total, origins[0])
    metrics = {"arima_by_agent": backtest.score(total, summed, scale)}
    metrics.update({name: backtest.score(total, f, scale) for name, f in backtest.baselines(total, origins).items()})
    ours = metrics["arima_by_agent"]["mae"]
    beats = all(ours < metrics[b]["mae"] for b in ("seasonal_naive", "profile"))
    for name, m in metrics.items():
        log(f"  total, {name:<15} {_line(m)}")
    return {"created": datetime.now().isoformat(timespec="seconds"), "device_id": device_id, "agents": out,
            "total": metrics, "beats_baselines": beats, "folds": len(origins),
            "thresholds_w": patterns.thresholds(total),
            "run": _run_record(ckpt, started, not_converged=stuck, **extra)}


def forecast(saved, agents, hourly, cfg, hours=None, paths=CONFIG["forecast"]["paths"], now=None):
    """The bill forecast from the current hour to the end of the billing cycle (or `hours` ahead).

    Returns (hourly table, summary): per hour, each agent's kWh and the total kWh and pesos with
    their range and usage level; the summary has totals for the next day, week and rest of the
    cycle, the cost per agent, and the projected bill (baseline + AI so far + AI still to come).
    Hours between the last reading and now are unknown, and bridged by the models.
    """
    now = now or pd.Timestamp.now(tz=settings.TZ).tz_localize(None).floor("h")
    if agents.index[-1] < now - pd.Timedelta(hours=1):
        agents = agents.reindex(pd.date_range(agents.index[0], now - pd.Timedelta(hours=1), freq="h"))
    t = bill.tariff(cfg)
    cycle_start, cycle_end = bill.billing_cycle(now.date(), t["cycle_start_day"])
    first = agents.index[-1] + pd.Timedelta(hours=1)
    if hours is None:
        hours = int((pd.Timestamp(cycle_end) + pd.Timedelta(days=1) - first) / pd.Timedelta(hours=1))
    steps = max(1, min(hours, MAX_HOURS))

    index = pd.date_range(first, periods=steps, freq="h")
    total_paths = np.zeros((steps, paths))
    by_agent = {}
    for seed, name in enumerate(agents.columns):
        m = model.Model.from_dict(saved["agents"][name]["model"])
        sims = m.simulate(agents[name], steps, paths=paths, seed=seed)
        total_paths += sims
        by_agent[name] = np.median(sims, axis=1)
    table = bill.hourly_bill(total_paths, index, t, saved["thresholds_w"], by_agent)
    # Totals are at least as uncertain as the held-out day totals were wrong.
    error = saved["total"]["arima_by_agent"]["day_total_error"] or 0.0
    totals = bill.totals(total_paths, index, t, today=now.date(), rel_error=error)
    rate = bill.hourly_rates(index, t).to_numpy()
    in_cycle = index.date <= cycle_end
    agent_costs = {name: round(float((wh / 1000 * rate)[in_cycle].sum()), 2) for name, wh in by_agent.items()}
    summary = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "device_id": saved["device_id"], "from": str(index[0]), "to": str(index[-1]), "tariff": t,
        "totals": totals, "cost_by_agent_rest_of_cycle": agent_costs,
        "bill": bill.projected_bill(hourly, total_paths, index, t, cfg.BASELINE_BILL, cycle_start, cycle_end, now,
                                    rel_error=error),
        "backtest_day_total_error": error,
        "levels": table["level"].value_counts().to_dict(),
        "models": {name: a["chosen"] for name, a in saved["agents"].items()},
        "beats_baselines": saved["beats_baselines"],
        "model_trained": saved["created"], "bill_settings": bill_settings(cfg),
    }
    return table, summary
