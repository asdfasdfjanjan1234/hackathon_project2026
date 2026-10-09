import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from wattcast import backtest, bill, features, model, patterns, pipeline

SMALL = model.Spec((1, 0, 0), (1, 0, 0, 24))
QUIET = dict(log=lambda *_: None)


def test_routine_profile_learns_the_hours_of_the_week(agents):
    ollama = np.log1p(agents["Ollama"])
    routine = np.array(features.routine_profile(ollama))
    assert routine.shape == (7, 24)
    assert routine[1, 14] > 2 and routine[3, 14] > 2            # Tuesday and Thursday afternoons
    assert routine[0, 14] < routine[1, 14] / 4 and routine[1, 3] < 0.1  # not Monday afternoon or Tuesday night
    inputs = features.calendar(pd.date_range("2026-12-24", periods=48, freq="h"), routine)
    assert inputs.loc["2026-12-25 10:00", "holiday"] == 1 and inputs.loc["2026-12-24 10:00", "routine"] == routine[3, 10]


def test_routine_smoothing_adapts_to_how_regular_the_series_is():
    index = pd.date_range("2026-09-07", periods=4 * 168, freq="h")  # four weeks from a Monday
    tuesday_2pm = (index.dayofweek == 1) & (index.hour == 14)
    regular = pd.Series(np.where(tuesday_2pm, 3.0, 0.0), index=index)  # the same every week
    rng = np.random.default_rng(1)
    noisy = pd.Series(rng.normal(0, 1, len(index)), index=index)       # no routine at all
    noisy[tuesday_2pm & (index < "2026-09-14")] = 3.0                   # one high Tuesday, by chance
    assert np.array(features.routine_profile(regular))[1, 14] > 2.7    # kept: it happens every week
    assert np.array(features.routine_profile(noisy))[1, 14] < 1.0      # smoothed away: it was noise


def test_a_day_seen_once_is_trusted_when_the_days_seen_twice_are_regular(agents):
    """Under two weeks of readings: Tuesday has been seen twice, Thursday once. The agent runs only
    on Tuesday and Thursday afternoons, at about 22 W."""
    y = agents["Ollama"].iloc[:10 * 24]  # Monday Sep 7 through Wednesday Sep 16
    routine = np.array(features.routine_profile(np.log1p(y)))
    assert routine[3, 14] > 0.9 * np.log1p(22)   # Thursday 2 PM, seen once, kept nearly in full
    assert routine[4, 14] < 0.1                  # Friday 2 PM, seen once and idle, stays idle

    for spec in (model.ROUTINE_ONLY, SMALL):
        f = model.fit(y, spec).forecast(y, 48)["median"]  # Thursday Sep 17 and Friday Sep 18
        assert 15 < f["2026-09-17 14:00"] < 30, spec.label   # close to the 22 W it draws
        assert f["2026-09-18 14:00"] < 1, spec.label         # and none on the day it isn't used


def test_held_out_days_are_forecast_about_as_well_as_the_hour_of_week_average(agents):
    """The per-agent models, routine re-learned before each held-out day, on a perfectly regular
    week: they should be in the same range as the plain hour-of-week average, not far behind it."""
    total = agents.sum(axis=1, min_count=1)
    origins = backtest.usable_origins(total, 5)
    summed = {p: 0.0 for p in origins}
    for name in agents.columns:
        forecasts = backtest.evaluate(agents[name], model.ROUTINE_ONLY, origins)["forecasts"]
        summed = {p: summed[p] + forecasts[p] for p in origins}
    scale = backtest.scale(total, origins[0])
    ours = backtest.score(total, summed, scale)
    base = {k: backtest.score(total, f, scale) for k, f in backtest.baselines(total, origins).items()}
    assert ours["mae"] < 0.5 * base["seasonal_naive"]["mae"]
    assert ours["mae"] < 1.5 * base["profile"]["mae"]
    assert ours["day_total_error"] < 0.25


def test_fit_forecast_and_round_trip(agents):
    y = agents["Claude Code"]
    m = model.fit(y, SMALL)
    assert m.exog == [] and "routine" not in m.params  # no PH holiday in these weeks; the routine has no multiplier
    f = m.forecast(y, 48)
    assert len(f) == 48 and f.index[0] == y.index[-1] + pd.Timedelta(hours=1)
    assert (f["low"] <= f["median"]).all() and (f["median"] <= f["high"]).all() and (f["low"] >= 0).all()
    # The two days after the data are a Monday and a Tuesday: work hours are forecast heavier than nights.
    assert f["median"][f.index.hour == 11].mean() > 5 * f["median"][f.index.hour == 3].mean()
    again = model.Model.from_dict(json.loads(json.dumps(m.to_dict()))).forecast(y, 48)
    pd.testing.assert_frame_equal(f, again)
    warm = model.fit(y, SMALL, start=m.params)
    assert warm.trained["warm_start"] and set(warm.params) == set(m.params)


def test_the_forecast_follows_each_agents_time_of_use(agents):
    m = model.fit(agents["Ollama"], model.ROUTINE_ONLY)
    f = m.forecast(agents["Ollama"], 7 * 24)["median"]  # the week after the data: Monday to Sunday
    tuesday_afternoon = f[(f.index.dayofweek == 1) & (f.index.hour == 14)].iloc[0]
    monday_afternoon = f[(f.index.dayofweek == 0) & (f.index.hour == 14)].iloc[0]
    assert tuesday_afternoon > 10 and tuesday_afternoon > 15 * monday_afternoon
    assert model.ROUTINE_ONLY.label == "Routine only"


def test_backtest_scores_model_and_baselines(wh):
    origins = backtest.usable_origins(wh, 3)
    assert len(origins) == 3
    r = backtest.evaluate(wh, SMALL, origins)
    assert r["metrics"]["hours"] > 0 and r["metrics"]["mase"] >= 0
    for forecasts in backtest.baselines(wh, origins).values():
        assert backtest.score(wh, forecasts, backtest.scale(wh, origins[0]))["mae"] >= 0


def test_finetune_fits_one_model_per_agent_and_scores_the_total(agents, wh):
    with pytest.raises(ValueError, match="needs 72 hours"):
        pipeline.check_enough(wh.iloc[:48])
    luzon = [(SMALL, model.fit(wh, SMALL).params)]
    saved = pipeline.finetune(agents, 1, luzon, folds=3, top=1, **QUIET)
    assert list(saved["agents"]) == ["Ollama", "Claude Code"]
    for a in saved["agents"].values():
        assert {(t["spec"], t["start"]) for t in a["tried"]} == {
            ("Routine only", "cold"), (SMALL.label, "warm"), (SMALL.label, "cold")}
        assert a["chosen"]["spec"] == a["tried"][0]["spec"]
    assert set(saved["total"]) == {"arima_by_agent", "seasonal_naive", "profile"}
    # On data with a day-of-week routine the per-agent models beat "same hour yesterday".
    assert saved["total"]["arima_by_agent"]["mae"] < saved["total"]["seasonal_naive"]["mae"]
    json.dumps(saved)  # everything saved is plain JSON


def test_a_fit_records_its_iterations_and_whether_it_converged(agents):
    y, seen = agents["Claude Code"], []
    m = model.fit(y, SMALL, on_iteration=lambda number, loglike: seen.append((number, loglike)))
    t = m.trained
    assert t["converged"] and 1 <= t["iterations"] <= t["max_iterations"] == model.MAXITER
    assert [n for n, _ in seen] == list(range(1, len(seen) + 1)) and len(seen) == t["iterations"]
    assert seen[-1][1] >= seen[0][1] and seen[-1][1] == pytest.approx(t["loglike"], abs=0.01)  # it improved
    assert pipeline.fit_note(t) == f"  [{t['iterations']} iterations]"

    capped = model.fit(y, SMALL, maxiter=1).trained  # stopped after one iteration, before converging
    assert not capped["converged"] and capped["iterations"] <= 1 and capped["loglike"] < t["loglike"]
    assert "NOT converged" in pipeline.fit_note(capped) and "of 1 iterations" in pipeline.fit_note(capped)
    assert pipeline.fit_note({"aic": 1.0}) == ""  # a checkpoint from before iterations were recorded


def test_training_shows_iterations_when_asked_and_reports_fits_that_did_not_converge(wh, monkeypatch):
    log = []
    result = pipeline.pretrain(wh, [SMALL], folds=2, log=log.append)
    assert not any("iteration " in line for line in log)  # off by default
    assert "iterations]" in log[0] and result["ranking"][0]["converged"] and result["run"]["not_converged"] == []

    monkeypatch.setitem(pipeline.CONFIG["model"], "show_iterations", True)
    log.clear()
    pipeline.pretrain(wh, [SMALL], folds=2, ckpt=pipeline.luzon_checkpoints(fresh=True), log=log.append)
    assert any("fitting SARIMA(1,0,0)(1,0,0,24) for the backtest" in line for line in log)
    assert sum("log-likelihood" in line for line in log) >= 2

    real = model.fit
    monkeypatch.setattr(backtest, "fit", lambda y, spec, **kw: real(y, spec, **{**kw, "maxiter": 1}))
    capped = pipeline.pretrain(wh, [SMALL], folds=2, ckpt=pipeline.luzon_checkpoints(fresh=True), log=log.append)
    assert capped["run"]["not_converged"] == ["SARIMA(1,0,0)(1,0,0,24) (backtest)"]


def test_routine_only_can_be_kept_for_comparison_but_never_chosen(agents, monkeypatch):
    y, luzon = agents["Ollama"], [(SMALL, None)]
    origins = backtest.usable_origins(y, 3)
    args = ("Ollama", y, origins, luzon, 1, "test", lambda *_: None)
    allowed = pipeline._finetune_agent(pipeline.device_checkpoints(1), *args)
    assert allowed[0]["spec"] == "Routine only"  # on this perfectly regular agent the routine alone wins
    monkeypatch.setitem(pipeline.CONFIG["device"], "allow_routine_only", False)
    arima_only = pipeline._finetune_agent(pipeline.device_checkpoints(1), *args)
    assert arima_only[0]["spec"] == SMALL.label and arima_only[-1]["spec"] == "Routine only"


def test_a_fit_that_fails_is_skipped_and_not_retried(agents, monkeypatch):
    y, ar1 = agents["Claude Code"], model.Spec((1, 0, 0), (0, 0, 0, 0))
    real, calls = backtest.evaluate, []

    def failing_when_warm(y, spec, origins, start=None, **kw):
        calls.append((spec.label, bool(start)))
        if start:  # e.g. Luzon coefficients that aren't valid for this structure
            raise np.linalg.LinAlgError("Schur decomposition solver error.")
        return real(y, spec, origins, start=start, **kw)

    monkeypatch.setattr(backtest, "evaluate", failing_when_warm)
    args = ("Claude Code", y, backtest.usable_origins(y, 2), [(ar1, {"ar.L1": 1.56})], 1, "test")
    log = []
    tried = pipeline._finetune_agent(pipeline.device_checkpoints(1), *args, log.append)
    assert {(t["spec"], t["start"]) for t in tried} == {("Routine only", "cold"), (ar1.label, "cold")}
    assert any("warm  could not be fitted (LinAlgError)" in line for line in log)
    # A resumed run loads the two fits and the recorded failure: nothing is fitted or failed again.
    pipeline._finetune_agent(pipeline.device_checkpoints(1), *args, log.append)
    assert len(calls) == 3


def test_totals_pricing_flat_and_peak_offpeak():
    index = pd.date_range("2026-10-12 00:00", periods=24, freq="h")  # a Monday
    flat = {"tariff": "flat", "rate": 12.0, "peak_rate": 13.59, "offpeak_rate": 9.86, "cycle_start_day": 1}
    constant = np.full((24, 3), 100.0)  # 100 Wh every hour on every path
    t = bill.totals(constant, index, flat, today=index[0].date())
    assert t["next_24_hours"]["kwh"] == pytest.approx(2.4)
    assert t["next_24_hours"]["cost"] == pytest.approx(28.8)

    pop = {**flat, "tariff": "pop"}
    rates = bill.hourly_rates(index, pop)
    assert rates[pd.Timestamp("2026-10-12 10:00")] == 13.59   # Monday 10 AM: peak
    assert rates[pd.Timestamp("2026-10-12 22:00")] == 9.86    # Monday 10 PM: off-peak
    assert bill.totals(constant, index, pop, today=index[0].date())["next_24_hours"]["cost"] == pytest.approx(
        0.1 * (13 * 13.59 + 11 * 9.86), abs=0.005)  # pesos, rounded to centavos


def test_total_ranges_are_at_least_as_wide_as_the_backtest_error():
    index = pd.date_range("2026-10-12 00:00", periods=24, freq="h")
    flat = {"tariff": "flat", "rate": 10.0, "peak_rate": 0, "offpeak_rate": 0, "cycle_start_day": 1}
    paths = np.full((24, 50), 100.0) + np.linspace(-1, 1, 50)  # futures that barely differ: 24 +/- 0.24 pesos
    narrow = bill.totals(paths, index, flat, today=index[0].date())["next_24_hours"]
    assert narrow["cost_high"] - narrow["cost_low"] < 0.5
    wide = bill.totals(paths, index, flat, today=index[0].date(), rel_error=0.25)["next_24_hours"]
    assert (wide["cost"], wide["cost_low"], wide["cost_high"]) == (24.0, 18.0, 30.0)  # +/- 25% of the median


def test_forecast_projects_the_cycle_bill(agents, wh):
    luzon = [(SMALL, None)]
    saved = pipeline.finetune(agents, 1, luzon, folds=2, top=1, **QUIET)
    hourly = pd.DataFrame({"measured_h": 1.0, "ai_wh": wh.fillna(0), "scale": 1.0, "wh": wh})
    cfg = SimpleNamespace(ELECTRICITY_RATE=12.0, POP_PEAK_RATE=0, POP_OFFPEAK_RATE=0, TARIFF="flat",
                          BILLING_CYCLE_START_DAY=1, BASELINE_BILL=1500.0)
    now = agents.index[-1] + pd.Timedelta(hours=1)  # 2026-09-21 00:00, cycle Sep 1 - Sep 30
    table, summary = pipeline.forecast(saved, agents, hourly, cfg, paths=100, now=now)

    assert table.index[0] == now and table.index[-1] == pd.Timestamp("2026-09-30 23:00")
    assert {"kwh: Ollama", "kwh: Claude Code", "cost", "cost_low", "cost_high", "level", "peak"} <= set(table.columns)
    b = summary["bill"]
    assert b["ai_cost_so_far"] == pytest.approx(wh.fillna(0).sum() / 1000 * 12.0, abs=0.01)
    assert b["projected_bill"] == pytest.approx(1500 + b["ai_cost_so_far"] + b["ai_cost_remaining"], abs=0.02)
    assert b["projected_bill_low"] <= b["projected_bill"] <= b["projected_bill_high"]
    error = saved["total"]["arima_by_agent"]["day_total_error"]
    assert summary["backtest_day_total_error"] == error
    assert b["ai_cost_remaining_high"] >= round(b["ai_cost_remaining"] * (1 + error), 2) - 0.01
    assert b["forecast_reaches_cycle_end"] and b["hours_elapsed"] == 20 * 24
    costs = summary["cost_by_agent_rest_of_cycle"]
    assert set(costs) == {"Ollama", "Claude Code"} and all(c > 0 for c in costs.values())
    # Ollama is forecast only where it's used: Tuesday afternoon, not Monday afternoon.
    assert table.loc["2026-09-22 14:00", "kwh: Ollama"] > 15 * table.loc["2026-09-21 14:00", "kwh: Ollama"]


def test_usage_levels_and_agent_study(agents, wh):
    th = patterns.thresholds(wh)
    levels = patterns.level_of(pd.Series([0.2, th["light_max_w"], th["moderate_max_w"] + 1, np.nan]), th)
    assert list(levels) == ["idle", "light", "heavy", None]
    hourly = pd.DataFrame({"measured_h": 1.0, "ai_wh": wh.fillna(0), "scale": 1.0, "wh": wh})
    long = agents.fillna(0).rename_axis("hour").reset_index().melt("hour", var_name="app", value_name="wh")
    by_app = long.assign(name=long["app"], kind="cloud")
    report = patterns.study_device(hourly, by_app, agents)
    assert sum(lv["hours"] for lv in report["levels"]) == wh.notna().sum()
    ollama = next(a for a in report["agents"] if a["agent"] == "Ollama")
    assert set(ollama["busiest_hours"]) <= {13, 14, 15, 16} and ollama["weekend_avg_w"] == 0
    assert ollama["energy_in_meralco_peak_hours"] == 1  # weekday afternoons are all peak hours
    assert "## AI agents" in patterns.device_markdown(1, report)
