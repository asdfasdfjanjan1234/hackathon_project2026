"""Held-out check: forecast the next HORIZON hours from the start of each of the last few days,
using only the hours before, and compare with two simple baselines:

    seasonal_naive   the same hour the day before
    profile          the average of that hour of the week so far (else that hour of day)

Scores, over the measured hours that were held out:
    mae, rmse        average and root-mean-square error per hour, in the series' units
    wape             total absolute error / total actual: error as a share of the energy
    mase             mae / the in-sample error of "same hour yesterday" (below 1 beats it)
    day_total_error  average |forecast - actual| of each held-out day's total, as a share of the
                     actual: closest to "how far off is the bill"
"""

import numpy as np
import pandas as pd

from .config import CONFIG
from .model import DAY, MAXITER, fit

HORIZON = CONFIG["backtest"]["horizon_hours"]


def usable_origins(y, folds, horizon=HORIZON, min_train=2 * DAY):
    """Start positions of the last `folds` days of `y` (oldest first) that have hours to train on
    before them and at least one measured hour to score."""
    starts = [len(y) - horizon - i * DAY for i in range(folds)][::-1]
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
    last_day = y.iloc[pos - DAY:pos].to_numpy()
    naive = pd.Series(np.resize(last_day, horizon), index=y.index[pos:pos + horizon])
    return naive.fillna(profile(y, pos, horizon))  # yesterday wasn't measured at that hour


def baselines(y, origins, horizon=HORIZON):
    return {"seasonal_naive": {p: seasonal_naive(y, p, horizon) for p in origins},
            "profile": {p: profile(y, p, horizon) for p in origins}}


def scale(y, pos):
    """MASE's yardstick: the average change from the same hour a day earlier, before `pos`."""
    past = y.iloc[:pos]
    s = (past - past.shift(DAY)).abs().mean()
    return float(s) if pd.notna(s) and s > 0 else None


def score(y, forecasts, scale_value):
    errors, actuals, day_errors = [], [], []
    for f in forecasts.values():
        actual = y.reindex(f.index)
        seen = actual.notna()
        if not seen.any():
            continue
        errors.append((f[seen] - actual[seen]).to_numpy())
        actuals.append(actual[seen].to_numpy())
        if actual[seen].sum() > 0:
            day_errors.append(abs(f[seen].sum() - actual[seen].sum()) / actual[seen].sum())
    e, a = np.concatenate(errors), np.concatenate(actuals)
    mae = float(np.mean(np.abs(e)))
    return {"mae": round(mae, 4), "rmse": round(float(np.sqrt(np.mean(e ** 2))), 4),
            "wape": round(float(np.sum(np.abs(e)) / np.sum(np.abs(a))), 4) if np.sum(np.abs(a)) else None,
            "mase": round(mae / scale_value, 4) if scale_value else None,
            "day_total_error": round(float(np.mean(day_errors)), 4) if day_errors else None,
            "hours": int(len(e))}


def evaluate(y, spec, origins, horizon=HORIZON, start=None, maxiter=MAXITER, source="", on_iteration=None):
    """Fit `spec` on the hours before the first origin, then forecast `horizon` hours from each one.
    Returns {"model", "forecasts": {origin: series}, "metrics"}."""
    model = fit(y.iloc[:origins[0]], spec, start=start, maxiter=maxiter, source=source, on_iteration=on_iteration)
    forecasts = model.backtest_forecasts(y, origins, horizon)
    return {"model": model, "forecasts": forecasts, "metrics": score(y, forecasts, scale(y, origins[0]))}
