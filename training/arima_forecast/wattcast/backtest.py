"""Held-out check: forecast each of the last few windows of the series from its start, using only
the steps before, and compare with three simple baselines:

    seasonal_naive   the same time the day before
    profile          the average of that hour of the week so far (else that hour of day)
    last_value       the last known step, held for the whole window

A window is `horizon` steps: a day ahead for Luzon, a couple of hours for a device that has only
been read for a few (`horizon_hours` in config.json). Windows follow one another and end where the
series does. Before a day of readings exists there is no "day before", so seasonal_naive is the
profile then.

Scores, over the measured steps that were held out:
    mae, rmse           average and root-mean-square error per step, in the series' units
    wape                total absolute error / total actual: error as a share of the energy
    mase                mae / the in-sample error of "same time yesterday" (below 1 beats it)
    window_total_error  average |forecast - actual| of each held-out window's total, as a share of
                        the actual: closest to "how far off is the bill"
"""

import numpy as np
import pandas as pd

from .model import MAXITER, fit
from .steps import hours, per_day


def usable_origins(y, folds, horizon=None, min_train=None):
    """Start positions of the last `folds` windows of `horizon` steps in `y` (oldest first) that have
    `min_train` steps to train on before them and at least one measured step to score. By default a
    window is a day and two days come before the first."""
    horizon = horizon or per_day(y.index)
    min_train = 2 * per_day(y.index) if min_train is None else min_train
    starts = [len(y) - horizon * (i + 1) for i in range(folds)][::-1]
    return [p for p in starts if p >= min_train and y.iloc[p:p + horizon].notna().any()]


def profile(y, pos, horizon):
    past = y.iloc[:pos].dropna()
    index = y.index[pos:pos + horizon]
    if past.empty:
        return pd.Series(np.nan, index=index)
    by_week_hour = past.groupby([past.index.dayofweek, past.index.hour]).mean()
    by_hour = past.groupby(past.index.hour).mean()
    overall = past.mean()
    return pd.Series([by_week_hour.get((t.dayofweek, t.hour), by_hour.get(t.hour, overall)) for t in index],
                     index=index)


def seasonal_naive(y, pos, horizon):
    day, index = per_day(y.index), y.index[pos:pos + horizon]
    if pos < day:  # no day before yet
        return profile(y, pos, horizon)
    naive = pd.Series(np.resize(y.iloc[pos - day:pos].to_numpy(), len(index)), index=index)
    return naive.fillna(profile(y, pos, horizon))  # yesterday wasn't measured at that time


def last_value(y, pos, horizon):
    past = y.iloc[:pos].dropna()
    return pd.Series(past.iloc[-1] if len(past) else np.nan, index=y.index[pos:pos + horizon])


def baselines(y, origins, horizon=None):
    horizon = horizon or per_day(y.index)
    return {"seasonal_naive": {p: seasonal_naive(y, p, horizon) for p in origins},
            "profile": {p: profile(y, p, horizon) for p in origins},
            "last_value": {p: last_value(y, p, horizon) for p in origins}}


def scale(y, pos):
    """MASE's yardstick: the average change from the same time a day earlier, before `pos`. Before a
    day of readings exists, from the step before."""
    past = y.iloc[:pos]
    for lag in (per_day(y.index), 1):
        s = (past - past.shift(lag)).abs().mean()
        if pd.notna(s) and s > 0:
            return float(s)
    return None


def score(y, forecasts, scale_value):
    errors, actuals, window_errors = [], [], []
    for f in forecasts.values():
        actual = y.reindex(f.index)
        seen = actual.notna()
        if not seen.any():
            continue
        errors.append((f[seen] - actual[seen]).to_numpy())
        actuals.append(actual[seen].to_numpy())
        if actual[seen].sum() > 0:
            window_errors.append(abs(f[seen].sum() - actual[seen].sum()) / actual[seen].sum())
    e, a = np.concatenate(errors), np.concatenate(actuals)
    mae = float(np.mean(np.abs(e)))
    return {"mae": round(mae, 4), "rmse": round(float(np.sqrt(np.mean(e ** 2))), 4),
            "wape": round(float(np.sum(np.abs(e)) / np.sum(np.abs(a))), 4) if np.sum(np.abs(a)) else None,
            "mase": round(mae / scale_value, 4) if scale_value else None,
            "window_total_error": round(float(np.mean(window_errors)), 4) if window_errors else None,
            "hours": hours(len(e), y.index)}


def evaluate(y, spec, origins, horizon=None, start=None, maxiter=MAXITER, source="", on_iteration=None):
    """Fit `spec` on the steps before the first origin, then forecast `horizon` steps from each one.
    Returns {"model", "forecasts": {origin: series}, "metrics"}."""
    horizon = horizon or per_day(y.index)
    model = fit(y.iloc[:origins[0]], spec, start=start, maxiter=maxiter, source=source, on_iteration=on_iteration)
    forecasts = model.backtest_forecasts(y, origins, horizon)
    return {"model": model, "forecasts": forecasts, "metrics": score(y, forecasts, scale(y, origins[0]))}
