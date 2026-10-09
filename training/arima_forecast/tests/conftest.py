import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wattcast  # noqa: E402,F401  (puts the backend on the import path)


# The held-out windows the hourly tests use: a day each, after two days to fit on.
DAILY = {"horizon_hours": 24, "min_train_hours": 48}


def synthetic_agents(days=14, seed=0, start="2026-09-07"):
    """Made-up hourly Wh for tests only. "Claude Code": weekday work hours, light evenings.
    "Ollama": Tuesday and Thursday afternoons only. A few unknown hours in both."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=days * 24, freq="h")  # starts on a Monday
    weekday = index.dayofweek < 5
    work = (index.hour >= 9) & (index.hour < 18) & weekday
    evening = (index.hour >= 19) & (index.hour < 23)
    claude = np.where(work, 4.0, np.where(evening, 1.2, 0.1)) * rng.lognormal(0, 0.25, len(index))
    ollama = np.where(index.dayofweek.isin([1, 3]) & (index.hour >= 13) & (index.hour < 17), 22.0, 0.0)
    ollama = ollama * rng.lognormal(0, 0.15, len(index))
    agents = pd.DataFrame({"Ollama": ollama, "Claude Code": claude}, index=index)
    agents.iloc[rng.choice(len(index), size=len(index) // 25, replace=False)] = np.nan
    return agents


@pytest.fixture(autouse=True)
def artifacts_in_tmp(tmp_path, monkeypatch):
    """Models and checkpoints written by a test go to a temporary folder, never the real artifacts."""
    from wattcast import settings

    monkeypatch.setattr(settings, "DEVICE_DIR", str(tmp_path / "devices"))
    monkeypatch.setattr(settings, "LUZON_DIR", str(tmp_path / "luzon"))
    monkeypatch.setattr(settings, "LUZON_CHECKPOINTS", str(tmp_path / "luzon" / "checkpoints"))
    monkeypatch.setattr(settings, "LUZON_MODEL", str(tmp_path / "luzon" / "luzon_pretrained.json"))


@pytest.fixture
def agents():
    return synthetic_agents()


@pytest.fixture
def wh(agents):
    return agents.sum(axis=1, min_count=1).rename("wh")
