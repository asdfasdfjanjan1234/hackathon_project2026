"""Time steps. Every series is regular: one value per step of `step_minutes` (config.json), 15
minutes by default.

The setting decides the step of what's built from raw data: the device's readings (readings.py) and
Luzon's demand (iemop.py). Everything after that takes the step from the series it's given, so a
duration in config.json stays in hours (`horizon_hours`, `min_hours`, ...) and is counted in steps
of the series at hand.

A device's value for a step is the energy used in it (Wh), so steps add up to the bill. Its average
power in the step is that times the steps in an hour (patterns.watts).
"""

import os

import pandas as pd

from .config import CONFIG

HOUR = pd.Timedelta(hours=1)
MINUTES = CONFIG["step_minutes"]
STEP = pd.Timedelta(minutes=MINUTES)
PER_DAY = 24 * 60 // MINUTES


def step_of(index):
    """The step of a regular time index."""
    return pd.Timedelta(index.freq) if index.freq is not None else index[1] - index[0]


def minutes(index):
    return round(step_of(index) / pd.Timedelta(minutes=1))


def per_hour(index):
    """Steps in an hour of `index`: 4 at 15 minutes, 1 when hourly."""
    return round(HOUR / step_of(index))


def per_day(index):
    return 24 * per_hour(index)


def count(hours, index):
    """`hours` as a number of steps of `index`."""
    return round(hours * per_hour(index))


def hours(n, index):
    """`n` steps of `index` in hours."""
    return round(n / per_hour(index), 2)


def load(path, made_by):
    """The table saved at `path` by the script `made_by`, indexed by its `time` column, with a regular
    index at the configured step. A file saved at another step is an error: a model fitted on one
    step doesn't apply to another."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found: run {made_by} first")
    table = pd.read_csv(path, parse_dates=["time"], index_col="time")
    if len(table) > 1 and table.index.to_series().diff().min() != STEP:
        raise ValueError(f"{path} isn't in {MINUTES}-minute steps (step_minutes in config.json): "
                         "run the steps again, from 01_download_iemop.py")
    return table.asfreq(STEP)
