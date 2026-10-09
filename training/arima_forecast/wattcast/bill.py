"""Forecast AI energy -> the electricity bill: step by step, in totals, and for the billing cycle.

A step's energy (Wh) is priced at the rate of the clock hour it falls in, so the steps add up to the
bill whatever their length. The rate follows the household's tariff in backend/.env, using the backend's own code:
a flat ELECTRICITY_RATE, or Meralco Peak/Off-Peak (TARIFF=pop) with its schedule and rates
(cheap_hours.py), so when AI is used changes what it costs. Ranges come from simulated futures
(paths), so a total over many steps has its own range rather than the sum of each step's.

Simulated futures only vary step to step around the learned routine; they don't know the routine
itself may be off. So a total's range is never narrower than the backtest's error on the totals of
held-out windows (rel_error): the wider of the two is reported.

    projected bill = BASELINE_BILL (the bill without AI, from backend/.env)
                   + AI cost measured so far this billing cycle
                   + AI cost forecast for the time left in it
"""

from datetime import date

import numpy as np
import pandas as pd

from app.services.cheap_hours import is_peak, pop_rates
from app.services.forecasting import billing_cycle  # noqa: F401  (used by pipeline.forecast)

from .model import INTERVAL
from .patterns import level_of, watts
from .steps import hours

LOW_Q, HIGH_Q = (1 - INTERVAL) / 2, 1 - (1 - INTERVAL) / 2


def tariff(cfg):
    peak, off = pop_rates(cfg.ELECTRICITY_RATE, cfg.POP_PEAK_RATE, cfg.POP_OFFPEAK_RATE)
    return {"tariff": cfg.TARIFF, "rate": cfg.ELECTRICITY_RATE, "peak_rate": peak, "offpeak_rate": off,
            "cycle_start_day": cfg.BILLING_CYCLE_START_DAY}


def rates(index, t):
    """P/kWh for each step in `index` on tariff `t`."""
    if t["tariff"] != "pop":
        return pd.Series(float(t["rate"]), index=index)
    return pd.Series([t["peak_rate"] if is_peak(h.dayofweek, h.hour) else t["offpeak_rate"] for h in index],
                     index=index)


def forecast_table(paths_wh, index, t, th, by_agent=None):
    """The step-by-step table from simulated total AI Wh (steps x paths): kWh and pesos (median, low,
    high), P/kWh, whether the step is in a Meralco peak hour, the usage level expected, and each
    agent's median kWh (by_agent: {name: Wh per step})."""
    rate = rates(index, t)
    median = pd.Series(np.median(paths_wh, axis=1), index=index)
    kwh = pd.DataFrame({"kwh": median, "kwh_low": np.quantile(paths_wh, LOW_Q, axis=1),
                        "kwh_high": np.quantile(paths_wh, HIGH_Q, axis=1)}, index=index) / 1000
    out = kwh.copy()
    out["rate"] = rate
    out["peak"] = [is_peak(h.dayofweek, h.hour) for h in index]
    out["cost"], out["cost_low"], out["cost_high"] = kwh["kwh"] * rate, kwh["kwh_low"] * rate, kwh["kwh_high"] * rate
    out["level"] = level_of(watts(median), th)
    for name, wh in (by_agent or {}).items():
        out[f"kwh: {name}"] = np.asarray(wh) / 1000
    out.index.name = "time"
    return out


def windows(index, t, today=None):
    """{name: boolean mask over `index`} for the totals reported."""
    today = today or date.today()
    _, cycle_end = billing_cycle(today, t["cycle_start_day"])
    start = index[0]
    return {
        "next_24_hours": index < start + pd.Timedelta(hours=24),
        "next_7_days": index < start + pd.Timedelta(days=7),
        f"rest_of_cycle (to {cycle_end})": index.date <= cycle_end,
    }


def _range(values, digits=2, rel_error=0.0):
    """(median, low, high) of simulated totals, the range at least +/- rel_error around the median."""
    median = float(np.median(values))
    low = min(float(np.quantile(values, LOW_Q)), median * (1 - rel_error))
    high = max(float(np.quantile(values, HIGH_Q)), median * (1 + rel_error))
    return round(median, digits), round(max(low, 0.0), digits), round(high, digits)


def totals(paths_wh, index, t, today=None, rel_error=0.0):
    """{window: {hours, kwh, cost, cost_low, cost_high}} from simulated paths (steps x paths, Wh)."""
    cost = paths_wh / 1000 * rates(index, t).to_numpy()[:, None]
    out = {}
    for name, mask in windows(index, t, today).items():
        if not mask.any():
            continue
        c, low, high = _range(cost[mask].sum(axis=0), rel_error=rel_error)
        out[name] = {"hours": hours(int(mask.sum()), index), "kwh": _range(paths_wh[mask].sum(axis=0) / 1000, 4)[0],
                     "cost": c, "cost_low": low, "cost_high": high}
    return out


def projected_bill(energy, paths_wh, index, t, baseline_bill, cycle_start, cycle_end, now, rel_error=0.0):
    """This billing cycle's bill: baseline + AI measured so far + AI forecast for the time left.

    energy: the device's readings by step (readings.ai_energy); only measured energy counts toward
    "so far", so time the reader didn't run this cycle isn't in it.
    """
    start = pd.Timestamp(cycle_start)
    so_far = energy[(energy.index >= start) & (energy.index < index[0])]
    ai_so_far = float((so_far["ai_wh"] / 1000 * rates(so_far.index, t)).sum()) if len(so_far) else 0.0
    left = index.date <= cycle_end
    remaining = (paths_wh / 1000 * rates(index, t).to_numpy()[:, None])[left].sum(axis=0)
    rest, rest_low, rest_high = _range(remaining, rel_error=rel_error) if left.any() else (0.0, 0.0, 0.0)
    ai_cycle = ai_so_far + rest
    elapsed = max(int((now - start) / pd.Timedelta(hours=1)), 0)
    return {
        "cycle": {"start": str(cycle_start), "end": str(cycle_end)},
        "baseline_bill": float(baseline_bill),
        "ai_cost_so_far": round(ai_so_far, 2),
        "ai_cost_remaining": rest, "ai_cost_remaining_low": rest_low, "ai_cost_remaining_high": rest_high,
        "ai_cost_cycle": round(ai_cycle, 2),
        "projected_bill": round(baseline_bill + ai_cycle, 2),
        "projected_bill_low": round(baseline_bill + ai_so_far + rest_low, 2),
        "projected_bill_high": round(baseline_bill + ai_so_far + rest_high, 2),
        "ai_share_of_bill": round(ai_cycle / (baseline_bill + ai_cycle), 4) if baseline_bill + ai_cycle else None,
        "hours_measured_so_far": round(float(so_far["measured_h"].sum()), 1) if len(so_far) else 0.0,
        "hours_elapsed": elapsed,
        "forecast_reaches_cycle_end": bool(index[-1].date() >= cycle_end),
    }
