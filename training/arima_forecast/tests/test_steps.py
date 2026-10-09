"""The pipeline in 15-minute steps, on a device that has been read for under a day."""

import json
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from wattcast import backtest, bill, config, features, model, patterns, pipeline, readings, settings, steps

QUARTER = pd.Timedelta(minutes=15)
ARMA = model.Spec((1, 0, 1), (0, 0, 0, 0))
DAY_SEASON = model.Spec((1, 0, 0), (1, 0, 0, 96))
FLAT = {"tariff": "flat", "rate": 12.0, "peak_rate": 13.59, "offpeak_rate": 9.86, "cycle_start_day": 1}


def work_day(hours=10, seed=0, start="2026-10-09 09:00"):
    """Made-up Wh per 15-minute step for tests only, from 9 AM on a Friday. "Claude Code" works in
    bursts that carry over from one step to the next, around 2 W. "Ollama" runs from noon to 3 PM
    at about 30 W."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=hours * 4, freq="15min")
    burst = np.zeros(len(index))
    for t in range(1, len(index)):
        burst[t] = 0.7 * burst[t - 1] + rng.normal(0, 0.4)
    ollama = np.where((index.hour >= 12) & (index.hour < 15), 7.5, 0.0) * rng.lognormal(0, 0.1, len(index))
    return pd.DataFrame({"Ollama": ollama, "Claude Code": 0.5 * np.exp(burst)}, index=index)


def test_durations_are_counted_in_the_steps_of_the_series():
    quarters = pd.date_range("2026-10-09", periods=96, freq="15min")
    hourly = pd.date_range("2026-10-09", periods=24, freq="h")
    assert (steps.per_hour(quarters), steps.per_day(quarters), steps.count(2, quarters)) == (4, 96, 8)
    assert (steps.per_hour(hourly), steps.per_day(hourly), steps.count(2, hourly)) == (1, 24, 2)
    assert steps.hours(34, quarters) == 8.5 and steps.minutes(quarters) == 15
    assert steps.minutes(pd.DatetimeIndex(list(quarters[:3]))) == 15  # no frequency set: from its first two times
    assert steps.PER_DAY == 24 * 60 // config.CONFIG["step_minutes"]


def test_a_season_of_one_day_follows_the_step_and_structures_without_one_are_plain_arima():
    assert model._candidate([1, 0, 1], [1, 0, 1, "day"]) == model.Spec((1, 0, 1), (1, 0, 1, steps.PER_DAY))
    assert (ARMA.label, ARMA.season) == ("ARIMA(1,0,1)", 0)
    assert (DAY_SEASON.label, DAY_SEASON.season) == ("SARIMA(1,0,0)(1,0,0,96)", 96)
    assert model.ROUTINE_ONLY.season == 0
    assert any(s.season == steps.PER_DAY for s in model.CANDIDATES)
    assert all(s.season == 0 for s in model.CANDIDATES[:2])  # what --quick fits, and a device's first hours


def test_the_routine_counts_an_hour_once_however_short_the_steps():
    index = pd.date_range("2026-10-05", periods=5 * 24, freq="h")
    hourly = pd.Series(np.random.default_rng(3).normal(0, 1, len(index)), index=index)
    quarters = hourly.resample("15min").ffill()  # the same level through each hour, in four steps
    routine = features.routine_profile(quarters)
    assert routine == features.routine_profile(hourly)
    inputs = features.calendar(quarters.index, routine)
    assert inputs.loc["2026-10-07 14:45", "routine"] == routine[2][14]  # every step gets its hour's level


def test_fit_and_forecast_in_15_minute_steps():
    y = work_day(hours=24)["Claude Code"]
    m = model.fit(y, ARMA)
    assert (m.trained["step_minutes"], m.trained["hours"], m.trained["observed_hours"]) == (15, 24, 24)
    f = m.forecast(y, 8)
    assert len(f) == 8 and f.index[0] == y.index[-1] + QUARTER and f.index.freq == QUARTER
    assert (f["low"] <= f["median"]).all() and (f["median"] <= f["high"]).all() and (f["low"] >= 0).all()
    assert m.simulate(y, 8, paths=20).shape == (8, 20)


def test_held_out_windows_and_baselines_before_a_day_of_readings_exists():
    y = work_day(hours=12)["Claude Code"]  # 48 steps: no "same time yesterday" yet
    origins = backtest.usable_origins(y, folds=6, horizon=8, min_train=16)
    assert origins == [16, 24, 32, 40]            # two-hour windows, after four hours to fit on
    assert backtest.usable_origins(y, 3) == []    # windows of a day with two days before them: far too short
    base = backtest.baselines(y, origins, 8)
    assert set(base) == {"seasonal_naive", "profile", "last_value"}
    pd.testing.assert_series_equal(base["seasonal_naive"][16], base["profile"][16])  # no day before: the profile
    assert len(base["last_value"][24]) == 8 and (base["last_value"][24] == y.iloc[23]).all()
    assert backtest.scale(y, 16) == pytest.approx(y.iloc[:16].diff().abs().mean())  # from the step before
    r = backtest.evaluate(y, ARMA, origins, horizon=8)
    assert set(r["forecasts"]) == set(origins) and all(len(f) == 8 for f in r["forecasts"].values())
    assert r["metrics"]["hours"] == 8 and r["metrics"]["mase"] > 0 and r["metrics"]["window_total_error"] >= 0

    longer = work_day(hours=30)["Claude Code"]  # with a day before, "same time yesterday" is 96 steps back
    assert (backtest.seasonal_naive(longer, 100, 8).to_numpy() == longer.iloc[4:12].to_numpy()).all()
    assert backtest.scale(longer, 110) == pytest.approx((longer.iloc[:110] - longer.iloc[:110].shift(96)).abs().mean())


def test_pretraining_skips_a_seasonal_structure_the_series_is_too_short_for():
    y = work_day(hours=12)["Claude Code"]
    log = []
    result = pipeline.pretrain(y, [DAY_SEASON, ARMA], folds=2, horizon_hours=2, min_train_hours=4, log=log.append)
    assert "skipped" in log[0] and DAY_SEASON.label in log[0]
    assert [r["spec"] for r in result["ranking"]] == [ARMA.label]
    assert (result["step_minutes"], result["horizon_hours"], result["folds"]) == (15, 2, 2)
    assert result["run"]["data"]["hours"] == 12
    with pytest.raises(ValueError, match="luzon.horizon_hours"):
        pipeline.pretrain(y, [ARMA], folds=2, log=log.append)  # the luzon settings: a day ahead, after two days


def test_a_device_read_for_ten_hours_is_fine_tuned_and_its_bill_forecast():
    agents = work_day(hours=10)
    total = agents.sum(axis=1, min_count=1)
    with pytest.raises(ValueError, match="fine-tuning needs"):
        pipeline.check_enough(total.iloc[:steps.count(pipeline.MIN_HOURS, total.index) - 1])
    luzon = [(DAY_SEASON, None), (ARMA, {"ar.L1": 0.5, "ma.L1": 0.1, "sigma2": 0.5})]
    log = []
    saved = pipeline.finetune(agents, 1, luzon, top=2, log=log.append)  # the windows come from config.json

    assert "the last 3 windows of 2 hours, fitted on the 4 hours before" in log[0]
    assert (saved["step_minutes"], saved["folds"], saved["horizon_hours"]) == (15, 3, 2)
    assert saved["coverage"] == {"known_hours": 10, "days": 1, "hours_of_day": 10}
    for a in saved["agents"].values():
        tried = {(t["spec"], t["start"]) for t in a["tried"]}
        # The structure with a one-day season needs two days to fit on, so it isn't tried.
        assert tried == {("Routine only", "cold"), (ARMA.label, "warm"), (ARMA.label, "cold")}
        assert a["model"]["trained"]["step_minutes"] == 15 and a["model"]["trained"]["hours"] == 10
    assert set(saved["total"]) == {"arima_by_agent", "seasonal_naive", "profile", "last_value"}
    assert saved["total"]["arima_by_agent"]["hours"] == 6 and saved["total"]["arima_by_agent"]["mase"] > 0
    json.dumps(saved)  # everything saved is plain JSON

    energy = pd.DataFrame({"measured_h": 0.25, "ai_wh": total, "scale": 1.0, "wh": total})
    cfg = SimpleNamespace(ELECTRICITY_RATE=12.0, POP_PEAK_RATE=0, POP_OFFPEAK_RATE=0, TARIFF="flat",
                          BILLING_CYCLE_START_DAY=1, BASELINE_BILL=1500.0)
    now = agents.index[-1] + QUARTER  # 7 PM on Oct 9, cycle Oct 1 - Oct 31
    table, summary = pipeline.forecast(saved, agents, energy, cfg, hours=6, paths=50, now=now)
    assert len(table) == 24 and table.index[0] == now and table.index.name == "time"
    assert summary["step_minutes"] == 15 and summary["totals"]["next_24_hours"]["hours"] == 6
    assert summary["coverage"]["hours_of_day"] == 10 and summary["backtest_horizon_hours"] == 2
    assert table["kwh"].sum() == pytest.approx(table[["kwh: Ollama", "kwh: Claude Code"]].sum().sum(), rel=0.5)
    b = summary["bill"]
    assert b["ai_cost_so_far"] == pytest.approx(total.sum() / 1000 * 12.0, abs=0.01)  # steps add up to the energy
    assert b["hours_measured_so_far"] == 10 and b["hours_elapsed"] == 8 * 24 + 19

    full, to_cycle_end = pipeline.forecast(saved, agents, energy, cfg, paths=20, now=now)
    assert full.index[-1] == pd.Timestamp("2026-10-31 23:45") and to_cycle_end["bill"]["forecast_reaches_cycle_end"]
    assert to_cycle_end["bill"]["projected_bill"] >= 1500 + b["ai_cost_so_far"]

    with pytest.raises(ValueError, match="fine-tuned at 15-minute steps"):
        pipeline.forecast(saved, agents.resample("h").sum(), energy, cfg, now=now)


def test_the_bill_adds_up_whatever_the_step():
    index = pd.date_range("2026-10-12 00:00", periods=96, freq="15min")  # a Monday
    constant = np.full((96, 3), 25.0)  # 25 Wh every 15 minutes on every path: 100 W
    t = bill.totals(constant, index, FLAT, today=index[0].date())["next_24_hours"]
    assert (t["hours"], t["kwh"], t["cost"]) == (24, pytest.approx(2.4), pytest.approx(28.8))
    rates = bill.rates(index, {**FLAT, "tariff": "pop"})
    assert rates[pd.Timestamp("2026-10-12 10:45")] == 13.59 and rates[pd.Timestamp("2026-10-12 22:15")] == 9.86
    th = {"active_w": 1.0, "light_max_w": 50.0, "moderate_max_w": 150.0}
    table = bill.forecast_table(constant, index, FLAT, th, {"Ollama": np.full(96, 25.0)})
    assert (table["level"] == "moderate").all()  # 100 W: the level comes from the power, not the 25 Wh of a step
    assert table["cost"].sum() == pytest.approx(28.8) and table["kwh: Ollama"].sum() == pytest.approx(2.4)


def test_an_agent_gets_its_own_model_after_enough_hours_in_use():
    index = pd.date_range("2026-10-09 09:00", periods=16, freq="15min")
    energy = pd.DataFrame({"measured_h": 0.25, "ai_wh": 0.0, "scale": 1.0}, index=index)
    need = steps.count(readings.MIN_USED_HOURS, index)  # steps in use, for the configured hours
    rows = ([{"time": t, "app": "Claude Code", "name": "Claude Code", "kind": "client", "wh": 0.5} for t in index[:need]]
            + [{"time": t, "app": "Codex", "name": "Codex", "kind": "client", "wh": 0.5} for t in index[:need - 1]]
            # 0.01 Wh in 15 minutes is 0.04 W: below the 0.05 W that counts as in use.
            + [{"time": t, "app": "GitHub Copilot", "name": "GitHub Copilot", "kind": "client", "wh": 0.01} for t in index])
    agents = readings.agent_series(energy, pd.DataFrame(rows))
    assert list(agents.columns) == ["Claude Code", readings.OTHER]
    assert agents[readings.OTHER].iloc[0] == pytest.approx(0.51)


def test_usage_levels_come_from_power_at_any_step():
    index = pd.date_range("2026-10-09 09:00", periods=8, freq="15min")
    wh = pd.Series([0.1, 0.1, 5, 5, 10, 10, 20, np.nan], index=index)
    w = patterns.watts(wh)
    assert w.iloc[2] == 20  # 5 Wh in 15 minutes
    assert list(patterns.level_of(w, patterns.thresholds(w)))[:2] == ["idle", "idle"]  # 0.4 W
    energy = pd.DataFrame({"measured_h": 0.25, "ai_wh": wh.fillna(0), "scale": 1.0, "wh": wh})
    by_app = pd.DataFrame({"time": index, "app": "Ollama", "name": "Ollama", "kind": "local", "wh": wh.fillna(0)})
    report = patterns.study_device(energy, by_app, readings.agent_series(energy, by_app))
    assert report["coverage"]["measured_hours"] == 1.75 and report["coverage"]["step_minutes"] == 15
    assert sum(lv["hours"] for lv in report["levels"]) == 1.75
    assert report["total_kwh"] == pytest.approx(wh.sum() / 1000, abs=1e-5)
    assert report["agents"][0]["avg_w_when_used"] == pytest.approx(w.mean(), abs=1e-3)
    assert "15-minute steps" in patterns.device_markdown(1, report)


def test_models_and_files_from_another_step_are_refused(tmp_path):
    assert pipeline.load_luzon()[0] == (model.CANDIDATES[0], None)  # before pre-training
    os.makedirs(settings.LUZON_DIR)
    with open(settings.LUZON_MODEL, "w") as f:
        json.dump({"step_minutes": 60, "ranking": []}, f)
    with pytest.raises(ValueError, match="pre-trained at 60-minute steps"):
        pipeline.load_luzon()
    ranked = {"order": [1, 0, 1], "seasonal_order": [0, 0, 0, 0], "params": {"ar.L1": 0.5}}
    with open(settings.LUZON_MODEL, "w") as f:
        json.dump({"step_minutes": steps.MINUTES, "ranking": [ranked]}, f)
    assert pipeline.load_luzon() == [(ARMA, {"ar.L1": 0.5})]

    path = str(tmp_path / "device_1_energy.csv")
    with pytest.raises(FileNotFoundError, match="run 02_export_readings.py first"):
        readings.load_energy(path)
    pd.DataFrame({"wh": 1.0}, index=pd.date_range("2026-10-09", periods=6, freq="h").rename("time")).to_csv(path)
    with pytest.raises(ValueError, match=f"isn't in {steps.MINUTES}-minute steps"):
        readings.load_energy(path)
    quarters = pd.DataFrame({"wh": 1.0}, index=pd.date_range("2026-10-09", periods=6, freq=steps.STEP).rename("time"))
    quarters.to_csv(path)
    loaded = readings.load_energy(path)
    assert len(loaded) == 6 and loaded.index.freq == steps.STEP and loaded.index.name == "time"
