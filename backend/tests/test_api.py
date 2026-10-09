import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True, USE_SAMPLE_DATA=True)
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
