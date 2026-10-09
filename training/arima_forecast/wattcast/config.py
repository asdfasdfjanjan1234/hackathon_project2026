"""Training configuration: one file, config.json, read by the notebook and every script.

DEFAULTS below is the full list of settings and their meaning; config.json overrides any of them
(a setting it doesn't mention keeps its default, and a name that isn't in DEFAULTS is an error, so a
typo can't silently do nothing). Every training run saves the configuration it used, with the
package versions and the bill settings, next to its checkpoints and inside the model file.
"""

import copy
import json
import os
import platform
from importlib import metadata

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

DEFAULTS = {
    # Clock time for readings and the tariff schedule.
    "timezone": "Asia/Manila",
    # Length of a time step, in minutes: every series has one value per step. 15 lets a device be
    # fine-tuned on a few hours of readings; 60 is hourly. One of 5, 10, 15, 20, 30, 60 (IEMOP's
    # data comes in 5-minute intervals). After changing it, run every step again, from 01.
    "step_minutes": 15,
    # Save every fitted candidate as it finishes, and reuse it when a run is repeated or resumed.
    "checkpoints": True,
    "luzon": {
        "days": 30,             # most recent days of Luzon demand to pre-train on
        "folds": 7,             # held-out windows in the backtest
        "horizon_hours": 24,    # length of each held-out window: how far ahead it's forecast
        "min_train_hours": 48,  # hours to fit on before the first held-out window, at least
        # ARIMA structures to try: [[p, d, q], [P, D, Q, season]]. The season is in steps, or "day"
        # for one day of steps (96 at 15 minutes); [0, 0, 0, 0] is no seasonal part. A structure with
        # a season is only tried on a series with two seasons to fit on, so the ones without are what
        # a device with a few hours of readings is fine-tuned with. --quick tries the first two.
        "candidates": [
            [[1, 0, 1], [0, 0, 0, 0]],
            [[2, 0, 1], [0, 0, 0, 0]],
            [[2, 0, 0], [0, 0, 0, 0]],
            [[1, 0, 1], [1, 0, 1, "day"]],
            [[2, 0, 0], [1, 0, 0, "day"]],
            [[0, 1, 1], [0, 1, 1, "day"]],
        ],
    },
    "device": {
        "gaps": "day",         # steps the reader didn't run: "day", "missing" or "zero" (readings.py)
        "min_coverage": 0.5,   # gaps "missing": share of a step the reader must have run
        "min_day_hours": 1.0,  # gaps "day": reader hours for a day to count as measured
        "folds": 6,            # held-out windows, at most
        "horizon_hours": 2,    # length of each held-out window
        "min_train_hours": 4,  # hours to fit on before the first held-out window, at least
        "top_structures": 2,   # Luzon structures tried per agent
        # May an agent's final model be its routine alone, with no AR/MA terms, when that forecasts
        # the held-out windows best? false: it's still scored for comparison, but an ARIMA is always chosen.
        "allow_routine_only": True,
        "min_hours": 6,        # known hours needed before fine-tuning
        "min_days": 1,
    },
    "agents": {
        "used_wh": 0.05,       # Wh an hour (average W) for the agent to count as in use in a step
        "min_used_hours": 2,   # hours in use for an agent to get its own model
        "min_share": 0.02,     # and this share of the AI energy
        "max_agents": 6,       # the rest are forecast together as "Other AI apps"
    },
    "levels": {"active_w": 1.0},  # below this average AI power a step is "idle"
    "model": {
        # ARIMA has no epochs: each fit is one optimization (maximum likelihood, L-BFGS) that stops
        # when it converges. Its iterations are the nearest thing to epochs; this is the most allowed.
        "maxiter": 200,
        "show_iterations": False,    # print the log-likelihood after every iteration of every fit
        "interval": 0.8,             # forecast ranges cover this share of outcomes
        "routine_prior_weight": 1.0,  # readings an hour of the week needs to count as much as its fallback
    },
    "forecast": {
        "paths": 500,       # simulated futures per agent, for the ranges
        "max_hours": 840,   # longest forecast (35 days)
    },
}
STEP_MINUTES = (5, 10, 15, 20, 30, 60)


def _merge(base, override, where=""):
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key not in base:
            raise ValueError(f"Unknown setting '{where}{key}' in config.json (see wattcast/config.py)")
        if isinstance(base[key], dict):
            if not isinstance(value, dict):
                raise ValueError(f"Setting '{where}{key}' in config.json must be a group of settings")
            out[key] = _merge(base[key], value, f"{where}{key}.")
        else:
            out[key] = value
    return out


def load(path=PATH):
    """DEFAULTS with config.json's values on top."""
    cfg = copy.deepcopy(DEFAULTS)
    if os.path.exists(path):
        with open(path) as f:
            cfg = _merge(DEFAULTS, json.load(f))
    if cfg["step_minutes"] not in STEP_MINUTES:
        raise ValueError(f"Setting 'step_minutes' in config.json must be one of {STEP_MINUTES}")
    return cfg


CONFIG = load()


def versions():
    return {"python": platform.python_version(),
            **{p: metadata.version(p) for p in ("numpy", "pandas", "scipy", "statsmodels", "holidays")}}


def bill_settings(cfg):
    """The backend settings (backend/.env) the bill forecast depends on. No database credentials."""
    return {"electricity_rate": cfg.ELECTRICITY_RATE, "tariff": cfg.TARIFF, "pop_peak_rate": cfg.POP_PEAK_RATE,
            "pop_offpeak_rate": cfg.POP_OFFPEAK_RATE, "baseline_bill": cfg.BASELINE_BILL,
            "billing_cycle_start_day": cfg.BILLING_CYCLE_START_DAY}


def snapshot(**extra):
    """What a run saves about how it was configured."""
    return {"config": copy.deepcopy(CONFIG), "versions": versions(), **extra}
