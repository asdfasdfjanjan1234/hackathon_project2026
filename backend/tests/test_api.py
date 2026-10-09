import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app()
    app.config.update(TESTING=True, USE_SAMPLE_DATA=True, DATABASE=str(tmp_path / "test.db"))
    return app.test_client()


def test_health(client):
    assert client.get("/api/health").json == {"status": "ok"}


def test_usage_returns_models(client):
    data = client.get("/api/usage").json
    assert data["by_model"]
    assert {"model", "kwh", "cost", "source"} <= data["by_model"][0].keys()


def test_forecast_adds_ai_cost_to_baseline(client):
    data = client.get("/api/forecast").json
    assert data["forecast_bill"] == pytest.approx(data["baseline_bill"] + data["ai_cost"])


def test_recommendations_lower_the_bill(client):
    data = client.get("/api/recommendations").json
    assert data["recommendations"]
    assert data["bill_with_recommendations"] < data["forecast_bill"]


def test_live_power(client):
    data = client.get("/api/live").json
    assert data["watts"] >= 0


def test_impact_parts_add_up(client):
    d = client.get("/api/impact").json
    assert d["rate_effect"] + d["ai_effect"] + d["other_effect"] == pytest.approx(d["increase"], abs=0.02)
    assert d["verdict"] in {"major", "contributing", "minor", "none", "no_increase"}


def test_rate_increase_is_not_blamed_on_ai():
    from app.services.impact import bill_impact
    daily = [{"kwh": 10, "source": "measured"}]
    d = bill_impact(daily, baseline_bill=1000, current_bill=1500, baseline_rate=10, current_rate=15)
    assert d["rate_effect"] == 500  # the whole increase is the rate going up
    assert d["ai_effect"] == 0 and d["verdict"] == "none"


def test_cloud_energy_not_counted_in_bill():
    from app.services.impact import bill_impact
    daily = [{"kwh": 500, "source": "estimated"}]
    d = bill_impact(daily, 1500, 2500, 12, 12)
    assert d["ai_effect"] == 0 and d["cloud_ai_kwh_estimated"] == 500


@pytest.mark.parametrize("window, days", [("7d", 7), ("30d", 30)])
def test_usage_window_narrows_daily_rows(client, window, days):
    data = client.get(f"/api/usage?range={window}").json
    assert data["window"]["id"] == window
    assert data["window_days"] == days
    dates = {r["date"] for r in data["daily"]}
    assert len(dates) == days
    assert all(data["window"]["start"] <= d <= data["window"]["end"] for d in dates)


def test_usage_month_to_date_starts_on_the_first(client):
    data = client.get("/api/usage?range=month").json
    assert data["window"]["start"].endswith("-01")
    assert all(r["date"] >= data["window"]["start"] for r in data["daily"])


def test_usage_shorter_window_uses_less_energy(client):
    week = sum(m["kwh"] for m in client.get("/api/usage?range=7d").json["by_model"])
    month = sum(m["kwh"] for m in client.get("/api/usage?range=30d").json["by_model"])
    assert 0 < week < month
