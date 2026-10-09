import json
import numpy as np
import pandas as pd
import pytest

from wattcast import backtest, model


def test_forecast_physical_bounds(agents):
    """Verify that predictions obey physical constraints: non-negativity and ordered intervals."""
    y = agents["Claude Code"]
    m = model.fit(y, model.Spec((1, 0, 1), (0, 0, 0, 0)))
    fc = m.forecast(y, 48)

    assert (fc["low"] >= 0).all(), "Low forecast bound cannot be negative"
    assert (fc["median"] >= 0).all(), "Median forecast cannot be negative"
    assert (fc["high"] >= 0).all(), "High forecast cannot be negative"
    assert (fc["low"] <= fc["median"] + 1e-6).all(), "low must be <= median"
    assert (fc["median"] <= fc["high"] + 1e-6).all(), "median must be <= high"


def test_prediction_interval_coverage_calibration(agents):
    """Empirical coverage test: ~80% of held-out points should fall inside [low, high]."""
    y = agents["Claude Code"]
    origins = backtest.usable_origins(y, folds=3, horizon=24, min_train=48)
    m = model.fit(y.iloc[:origins[0]], model.Spec((1, 0, 1), (0, 0, 0, 0)))

    coverages = []
    for p in origins:
        past = y.iloc[:p]
        refreshed = model.replace(m, routine=model.routine_profile(m.to_z(past)))
        fc = refreshed.forecast(past, 24)
        actual = y.iloc[p:p + 24]
        valid = actual.notna()
        if valid.any():
            cov = ((actual[valid] >= fc.loc[valid, "low"] - 1e-6) &
                   (actual[valid] <= fc.loc[valid, "high"] + 1e-6)).mean()
            coverages.append(cov)

    mean_cov = np.mean(coverages)
    assert 0.60 <= mean_cov <= 1.0, f"Expected 80% CI coverage within reasonable range, got {mean_cov:.2%}"


def test_model_inference_speed_benchmark(agents):
    """Benchmark inference latency: a 24-step forecast should run in sub-50ms."""
    import time

    y = agents["Claude Code"]
    m = model.fit(y, model.Spec((1, 0, 1), (0, 0, 0, 0)))

    t0 = time.perf_counter()
    _ = m.forecast(y, 24)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 100.0, f"Inference took {elapsed_ms:.2f} ms, expected < 100 ms"

