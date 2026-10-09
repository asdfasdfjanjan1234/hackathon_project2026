from datetime import datetime

import pytest

from app.services import cheap_hours as cp
from app.services import clean_hours as ch
from app.services.carbon import rec_co2
from app.services.recommendations import build_recommendations

GRID = {h: 450 if 10 <= h <= 14 else 750 if 18 <= h <= 22 else 600 if 8 <= h <= 17 else 650 for h in range(24)}
GRID[4] = GRID[5] = GRID[6] = 550  # the cleanest off-peak hours
EVENING_USE = {19: 0.2, 20: 0.4, 21: 0.2}  # kWh a day
POP = {"rate": 12.0, "tariff": "pop", "peak_rate": 14.0, "offpeak_rate": 10.0, "current_bill": 2500}
FLAT = {**POP, "tariff": "flat"}
TUESDAY_10PM = datetime(2026, 10, 13, 22, 0)


def _clean(use=EVENING_USE):
    return {"intensity": [{"hour": h, "g_per_kwh": GRID[h]} for h in range(24)], "plan": ch.plan(use, GRID)}


def test_meralco_schedule():
    assert cp.is_peak(0, 8) and cp.is_peak(5, 20) and not cp.is_peak(5, 21) and not cp.is_peak(2, 7)
    assert cp.is_peak(6, 18) and cp.is_peak(6, 19) and not cp.is_peak(6, 12) and not cp.is_peak(6, 20)
    assert cp.peak_share(12) == pytest.approx(6 / 7) and cp.peak_share(19) == 1 and cp.peak_share(2) == 0


def test_rates_are_estimated_from_the_regular_rate_unless_given():
    assert cp.pop_rates(12.0) == (12.0 + cp.PEAK_PREMIUM, 12.0 - cp.OFFPEAK_DISCOUNT)
    assert cp.pop_rates(12.0, 15.0, 9.0) == (15.0, 9.0)


def test_shifting_peak_ai_use_saves_on_pop():
    info = cp.cheap_hours(EVENING_USE, POP, now=TUESDAY_10PM)
    # 19:00 is peak every day, 20:00 six days of seven, 21:00 never
    peak_kwh = (0.2 * 1 + 0.4 * 6 / 7) * 30
    assert info["shift"]["savings"] == pytest.approx(peak_kwh * ch.SHIFTABLE_SHARE * 4.0, abs=0.01)
    assert info["ai"]["peak_share"] == pytest.approx(peak_kwh / 24, abs=0.001)
    assert info["now"] == {"rate": 10.0, "peak": False, "changes_at": "Wed 8 AM"}
    assert info["what_if_pop"] is None


def test_flat_rate_has_no_shift_but_shows_what_pop_would_cost():
    info = cp.cheap_hours(EVENING_USE, FLAT, now=TUESDAY_10PM)
    assert info["shift"] is None and info["now"] == {"rate": 12.0, "peak": None, "changes_at": None}
    assert {s["rate"] for s in info["schedule"]} == {12.0}
    w = info["what_if_pop"]
    assert w["cost_month_flat"] == pytest.approx(24 * 12.0)
    assert w["cost_month_pop_shifted"] < w["cost_month_pop"]
    assert w["household_kwh_month"] == 208 and not w["eligible"]
    assert cp.cheap_hours_rec(info) is None


def test_best_window_is_the_cleanest_off_peak_one_on_pop():
    best = cp.cheap_hours(EVENING_USE, POP, _clean(), now=TUESDAY_10PM)["best"]
    assert best["start_hour"] == 4 and best["g_per_kwh"] == 550
    assert "cleaner 10 AM – 1 PM" in best["reason"] and "peak" in best["reason"]


def test_best_window_without_grid_data_is_off_peak():
    best = cp.cheap_hours(EVENING_USE, POP, None, now=TUESDAY_10PM)["best"]
    assert best["label"] == "9 PM – 8 AM" and best["g_per_kwh"] is None


def test_best_window_on_flat_is_the_cleanest():
    best = cp.cheap_hours(EVENING_USE, FLAT, _clean(), now=TUESDAY_10PM)["best"]
    assert best["g_per_kwh"] == 450 and 10 <= best["start_hour"] <= 12


def test_cheap_hours_is_a_bill_recommendation_without_co2_saved():
    info = cp.cheap_hours(EVENING_USE, POP, _clean(), now=TUESDAY_10PM)
    forecast = {"by_model": [], "forecast_bill": 1500, "baseline_bill": 1500}
    recs = build_recommendations([], forecast, 12, 2000, {"cheap_hours": info})
    rec = next(r for r in recs if r["rule"] == "cheap hours")
    assert rec["scope"] == "bill" and rec["monthly_savings"] == info["shift"]["savings"] > 0
    assert "4 AM – 7 AM" in rec["message"]
    assert rec_co2(rec, 12, 0.7, 0.45) == {"co2_saved_kg": 0.0}


def test_no_recommendation_when_ai_runs_off_peak():
    info = cp.cheap_hours({1: 0.5, 23: 0.5}, POP, now=TUESDAY_10PM)
    assert info["shift"] is None and cp.cheap_hours_rec(info) is None
