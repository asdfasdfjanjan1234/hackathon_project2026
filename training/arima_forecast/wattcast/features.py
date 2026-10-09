"""Inputs known ahead of time, used for every step the model fits or forecasts.

    routine   the series' own weekly routine: its typical level in each of the 168 hours of the
              week (Monday 9 AM, Saturday 11 PM, ...), learned from the training steps. This is
              "when the user uses this AI agent, and how heavily"; ARIMA then models how each day
              departs from the routine. Every step in an hour gets that hour's level, and an hour
              counts as one reading (the average of its steps) however short the steps are: four
              15-minute steps of one afternoon are one look at that hour of the week, not four.
    holiday   a Philippine public holiday (the `holidays` package's PH calendar)

With little data an hour of the week has only one or two readings, so each one is pulled toward the
average for that hour on that kind of day (weekday or weekend), and that toward the hour of day.
An hour of the day that hasn't been read at all gets the series' overall level: a device read only
for an evening is forecast at that evening's average at every other time of day, until it's seen.
How hard it's pulled is estimated from the series itself: the noise among readings of the same
hour of the week, over the spread between hours. A regular agent (Tuesday and Thursday afternoons,
every week) keeps its day-specific hours; an irregular one is smoothed toward the average.
That's estimated over all the hours of the week together, so the days already seen twice show how
regular the agent is, and a day seen only once is trusted accordingly.
"""

import warnings

import numpy as np
import pandas as pd

with warnings.catch_warnings():
    warnings.simplefilter("ignore")  # holidays' notice about its 1.0 versioning; the version is pinned
    import holidays

from .config import CONFIG

# Readings an hour of the week needs before it counts as much as its fallback, when the series
# is too short to estimate that (fewer than MIN_CELLS hours with two or more readings).
PRIOR_WEIGHT = CONFIG["model"]["routine_prior_weight"]
WEIGHT_RANGE = (0.05, 10.0)
MIN_CELLS = 3


def _prior_weight(stats, fallback):
    """Readings a cell needs to count as much as its fallback: the variance among readings in the
    same cell over the variance between cells (the empirical-Bayes weight)."""
    multi = stats[stats["count"] >= 2]
    if len(multi) < MIN_CELLS:
        return PRIOR_WEIGHT
    within = float((multi["var"] * (multi["count"] - 1)).sum() / (multi["count"] - 1).sum())
    target = fallback[multi.index] if isinstance(fallback, pd.Series) else fallback
    between = float(((multi["mean"] - target) ** 2).mean() - within / multi["count"].mean())
    if between <= 0:
        return WEIGHT_RANGE[1]  # cells differ no more than noise would make them: lean on the fallback
    return float(np.clip(within / between, *WEIGHT_RANGE))


def _shrunk(stats, fallback):
    weight = _prior_weight(stats, fallback)
    count = stats["count"].fillna(0.0)
    return (stats["mean"].fillna(0.0) * count + fallback * weight) / (count + weight)


def routine_profile(z):
    """7 x 24 typical values of `z` (rows Monday..Sunday, columns hour 0..23), from its observed steps."""
    obs = z.dropna()
    if len(obs):
        obs = obs.groupby(obs.index.floor("h")).mean()  # one reading per clock hour, whatever the step
    frame = pd.DataFrame({"z": obs.to_numpy(), "day": obs.index.dayofweek, "hour": obs.index.hour})
    overall = float(frame["z"].mean()) if len(frame) else 0.0
    hours = pd.Index(range(24), name="hour")

    def level(rows, fallback):
        return _shrunk(rows.groupby("hour")["z"].agg(["mean", "count", "var"]).reindex(hours), fallback)

    hour_level = level(frame, overall)
    weekend = frame["day"] >= 5
    kind_level = {False: level(frame[~weekend], hour_level), True: level(frame[weekend], hour_level)}
    # Every hour of the week in one go: one weight for all 168, from the ones with repeat readings.
    cells = pd.MultiIndex.from_product([range(7), range(24)], names=["day", "hour"])
    stats = frame.groupby(["day", "hour"])["z"].agg(["mean", "count", "var"]).reindex(cells)
    fallback = pd.Series([kind_level[day >= 5][hour] for day, hour in cells], index=cells)
    return _shrunk(stats, fallback).to_numpy().reshape(7, 24).round(6).tolist()


def calendar(index, routine):
    """The inputs above for each step in `index`, given a routine from routine_profile()."""
    table = np.asarray(routine, dtype=float)
    ph = holidays.country_holidays("PH", years=range(index.min().year, index.max().year + 1))
    return pd.DataFrame({
        "routine": table[index.dayofweek, index.hour],
        "holiday": np.array([d in ph for d in index.date], dtype=float),
    }, index=index)
