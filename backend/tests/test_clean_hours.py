import io
import json
import urllib.error

import pytest

from app.services import clean_hours as ch
from app.services.recommendations import build_recommendations

# A grid that's cleanest at midday (solar) and dirtiest in the evening.
GRID = {h: 450 if 10 <= h <= 14 else 750 if 18 <= h <= 22 else 600 for h in range(24)}
EVENING_USE = {19: 0.2, 20: 0.4, 21: 0.2}  # kWh a day


def test_finds_the_cleanest_and_dirtiest_windows():
    p = ch.plan(EVENING_USE, GRID, window_hours=3)
    assert p["cleanest"]["g_per_kwh"] == 450 and 10 <= p["cleanest"]["start_hour"] <= 12
    assert p["dirtiest"]["g_per_kwh"] == 750
    assert p["weighted_g_per_kwh"] == 750 and p["peak_use_label"] == "8 PM"


def test_shifting_batch_work_saves_co2():
    s = ch.plan(EVENING_USE, GRID)["shift"]
    # 0.8 kWh a day × 30 × 30% shiftable × (750 - 450) g
    assert s["co2_saved_kg"] == pytest.approx(0.8 * 30 * 0.3 * 300 / 1000)


def test_no_shift_when_already_in_clean_hours():
    assert ch.plan({11: 0.5, 12: 0.5}, GRID)["shift"] is None


def test_no_plan_without_a_days_profile():
    assert ch.plan(EVENING_USE, {h: 500 for h in range(10)}) is None


def test_wraps_past_midnight():
    grid = {h: 300 if h in (23, 0, 1) else 600 for h in range(24)}
    assert ch.plan(EVENING_USE, grid)["cleanest"] == {"start_hour": 23, "end_hour": 2, "g_per_kwh": 300,
                                                        "label": "11 PM – 2 AM"}


def test_without_a_token_nothing_is_fetched_or_made_up(monkeypatch):
    monkeypatch.setattr(ch, "_get", lambda *a, **k: pytest.fail("fetched without a token"))
    info = ch.clean_hours(EVENING_USE, {"ELECTRICITYMAPS_TOKEN": "", "ELECTRICITYMAPS_ZONE": "PH-LU"})
    assert not info["configured"] and info["plan"] is None and info["intensity"] == []
    assert len(info["use"]) == 24
    assert ch.clean_hours_rec(info) is None


def _points(key):
    return {key: [{"datetime": f"2026-10-09T{h:02d}:00:00.000Z", "carbonIntensity": GRID[h]} for h in range(24)]}


def test_falls_back_to_history_when_forecast_isnt_on_the_plan(monkeypatch):
    ch._cache.clear()

    def get(path, zone, token, timeout=5):
        if path == "forecast":
            raise urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b'{"message": "not in plan"}'))
        if path == "history":
            return _points("history")
        return {"carbonIntensity": 600, "datetime": "2026-10-09T12:00:00.000Z"}

    monkeypatch.setattr(ch, "_get", get)
    info = ch.clean_hours(EVENING_USE, {"ELECTRICITYMAPS_TOKEN": "t", "ELECTRICITYMAPS_ZONE": "PH-LU"})
    assert info["source"] == "history" and info["error"] is None
    assert info["now"]["g_per_kwh"] == 600
    assert sum(1 for p in info["intensity"] if p["g_per_kwh"]) == 24


def test_reports_the_api_error(monkeypatch):
    ch._cache.clear()

    def get(*a, **k):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(json.dumps(
            {"message": "Invalid auth-token"}).encode()))

    monkeypatch.setattr(ch, "_get", get)
    info = ch.clean_hours(EVENING_USE, {"ELECTRICITYMAPS_TOKEN": "bad", "ELECTRICITYMAPS_ZONE": "PH-LU"})
    assert info["plan"] is None and info["error"] == "Invalid auth-token"


def test_clean_hours_becomes_a_carbon_recommendation():
    info = {"zone": "PH-LU", "source": "forecast", "plan": ch.plan(EVENING_USE, GRID)}
    forecast = {"by_model": [], "forecast_bill": 1500, "baseline_bill": 1500}
    recs = build_recommendations([], forecast, 12, 2000, {"clean_hours": info})
    rec = next(r for r in recs if r["rule"] == "clean hours")
    assert rec["scope"] == "carbon" and rec["monthly_savings"] == 0 and rec["co2_saved_kg"] > 0
