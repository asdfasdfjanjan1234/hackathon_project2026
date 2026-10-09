from datetime import date, timedelta

import pytest

from app import create_app
from app.services.forecasting import Trend, billing_cycle, forecast_bill

TODAY = date(2026, 10, 9)  # a Friday


def rows(model, values, end=TODAY - timedelta(days=1), **extra):
    """Daily rows ending on `end`, oldest first."""
    start = end - timedelta(days=len(values) - 1)
    return [{"date": (start + timedelta(days=i)).isoformat(), "model": model, "kwh": v, "kind": "local",
             "source": "measured", **extra} for i, v in enumerate(values)]


def test_billing_cycle_follows_the_meter_read_day():
    assert billing_cycle(date(2026, 10, 9), 1) == (date(2026, 10, 1), date(2026, 10, 31))
    assert billing_cycle(date(2026, 10, 9), 15) == (date(2026, 9, 15), date(2026, 10, 14))
    assert billing_cycle(date(2026, 1, 3), 15) == (date(2025, 12, 15), date(2026, 1, 14))
    assert billing_cycle(date(2026, 2, 28), 31) == (date(2026, 2, 28), date(2026, 3, 30))  # no Feb 31


def test_weekend_pattern_and_trend():
    # Weekdays 2 kWh, weekends 1 kWh, for four weeks.
    days = [TODAY - timedelta(days=i) for i in range(28, 0, -1)]
    t = Trend([(d, 1.0 if d.weekday() >= 5 else 2.0) for d in days])
    assert t.weekly and t.slope == pytest.approx(0, abs=1e-9)
    assert t.predict(date(2026, 10, 10)) == pytest.approx(1.0)  # Saturday
    assert t.predict(date(2026, 10, 12)) == pytest.approx(2.0)  # Monday


def test_trend_levels_off_instead_of_growing_forever():
    t = Trend([(TODAY - timedelta(days=i), 10.0 - i * 0.1) for i in range(20, 0, -1)])  # +0.1 kWh/day
    linear_in_a_year = t.predict(TODAY) + 0.1 * 365
    assert t.predict(TODAY + timedelta(days=30)) > t.predict(TODAY)
    assert t.predict(TODAY + timedelta(days=365)) < linear_in_a_year - 20


def test_cycle_series_adds_up_and_recommendations_only_change_the_future():
    daily = rows("llama3:8b", [1.0] * 30)
    f = forecast_bill(daily, rate=10, baseline_bill=1000, today=TODAY, budget=1200,
                      reductions={"llama3:8b": 0.5})
    assert f["forecast_bill"] == pytest.approx(1000 + 31 * 10)
    assert f["daily"][-1]["bill_to_date"] == pytest.approx(f["forecast_bill"])
    # Oct 1-9 unchanged, Oct 10-31 (22 days) at half the AI energy.
    assert f["forecast_bill_with_recommendations"] == pytest.approx(1000 + 9 * 10 + 22 * 5)
    assert f["budget_exceeded_on"] == "2026-10-29"  # ₱1,000/31 + ₱10 a day passes ₱1,200 on day 29
    assert f["budget_exceeded_on_with_recommendations"] is None
    assert [p["months"] for p in f["projections"]] == [1, 3, 12]
    assert f["projections"][0]["bill"] == pytest.approx(1000 + 30 * 10)  # November has 30 days
    assert f["projections"][0]["bill_with_recommendations"] == pytest.approx(1000 + 30 * 5)


def test_days_the_reader_was_off_are_not_counted_as_zero():
    # Measured on 3 days (2 kWh each); the reader was off on the other days in between.
    measured = [TODAY - timedelta(days=d) for d in (8, 4, 1)]
    daily = [{"date": d.isoformat(), "model": "Ollama · llama3:8b", "kwh": 2.0, "kind": "local",
              "source": "measured"} for d in measured]
    f = forecast_bill(daily, rate=10, baseline_bill=0, today=TODAY,
                      measured_days=[{"date": d.isoformat(), "hours": 8} for d in measured])
    assert f["by_model"][0]["avg_daily_kwh"] == pytest.approx(2.0)
    assert f["coverage"] == {"days_measured": 3, "hours_measured": 24, "first": measured[0].isoformat(),
                             "last": measured[-1].isoformat()}


def test_forecast_endpoint_uses_the_users_billing_cycle(tmp_path):
    app = create_app()
    app.config.update(TESTING=True, USE_SAMPLE_DATA=True, DATABASE=str(tmp_path / "t.db"))
    f = app.test_client().get("/api/forecast?cycle_start_day=15&budget=2000").json
    assert f["cycle"]["start_day"] == 15 and f["cycle"]["start"].endswith("-15")
    assert f["daily"][-1]["bill_to_date"] == pytest.approx(f["forecast_bill"], abs=0.05)
    assert f["equivalents"]["co2_kg"] > 0 and f["factors"]["aircon_watts"] > 0
