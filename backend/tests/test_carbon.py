import pytest

from app import create_app
from app.services.carbon import carbon_report, rec_co2

WINDOW = {"id": "7d", "start": "2026-10-01", "end": "2026-10-07", "days": 7}


def _rec(rule="smaller", scope="bill", savings=12.0, **extra):
    return {"action": "SWITCH", "rule": rule, "model": "Ollama · llama3:70b", "message": "",
            "monthly_savings": savings, "scope": scope, "alternative": False, **extra}


def _forecast(ai_kwh_per_day=1.0, days=30, days_left=10, saved_share=0.5, rate=12.0):
    ai_cost = ai_kwh_per_day * days * rate
    future = ai_kwh_per_day * (days_left - 1) * rate
    return {
        "cycle": {"start": "2026-10-01", "end": "2026-10-30", "days": days},
        "days_left": days_left,
        "baseline_bill": 1500,
        "daily": [{"date": f"2026-10-{i + 1:02d}", "ai_kwh": ai_kwh_per_day} for i in range(days)],
        "ai_cost_with_recommendations": ai_cost - future * saved_share,
        "projections": [{"months": 12, "ai_kwh": ai_kwh_per_day * 365,
                         "bill_with_recommendations": 12 * 1500 + ai_kwh_per_day * 365 * rate * (1 - saved_share)}],
    }


def test_bill_savings_become_co2_on_this_grid():
    # ₱12 saved at ₱12/kWh is 1 kWh, at 0.7 kg/kWh
    assert rec_co2(_rec(), rate=12, grid=0.7, datacenter=0.4) == {"co2_saved_kg": 0.7}


def test_moving_work_to_the_cloud_shifts_co2_instead_of_saving_it():
    d = rec_co2(_rec(rule="cloud"), rate=12, grid=0.7, datacenter=0.4)
    assert d["co2_saved_kg"] is None and d["co2_shifted_kg"] == 0.7


def test_datacenter_savings_use_the_datacenter_grid():
    d = rec_co2(_rec(rule="big cloud", scope="datacenter", savings=0, wh_saved=500), 12, 0.7, 0.4)
    assert d == {"co2_saved_kg": 0.2}


def test_report_splits_device_and_datacenter_co2():
    device = [{"date": "2026-10-02", "model": "Ollama · llama3:70b", "kind": "local", "kwh": 2.0,
               "active_hours": 4.0, "source": "measured"}]
    cloud = [{"date": "2026-10-03", "app": "Claude Code", "model": "claude-opus-5-5", "datacenter_wh": 1000}]
    r = carbon_report(device, cloud, _forecast(), [], WINDOW, rate=12, grid=0.7, datacenter=0.4, budget_kg=0)
    assert r["totals"]["device_kg"] == pytest.approx(1.4)
    assert r["totals"]["datacenter_kg"] == pytest.approx(0.4)
    assert len(r["daily"]) == 7
    top = r["by_model"][0]
    assert top["scope"] == "device" and top["g_per_active_hour"] == pytest.approx(350)
    assert r["budget"] is None


def test_recommendations_lower_projected_co2():
    r = carbon_report([], [], _forecast(), [{**_rec(), "co2_saved_kg": 0.7}], WINDOW,
                      rate=12, grid=0.7, datacenter=0.4, budget_kg=0)
    assert r["cycle"]["projected_kg_with_recommendations"] < r["cycle"]["projected_kg"]
    assert r["year"]["avoided_kg"] == pytest.approx(365 * 0.5 * 0.7, rel=1e-3)
    assert r["top_actions"][0]["co2_saved_kg"] == 0.7


@pytest.mark.parametrize("budget, status", [(100, "under"), (19, "fixed_by_recommendations"), (5, "over")])
def test_carbon_budget_status(budget, status):
    # 30 kWh a cycle at 0.7 = 21 kg; with recommendations 21 - 9 × 0.5 × 0.7 = 17.85 kg
    r = carbon_report([], [], _forecast(), [], WINDOW, rate=12, grid=0.7, datacenter=0.4, budget_kg=budget)
    assert r["budget"]["status"] == status
    assert (r["budget"]["exceeded_on"] is None) == (budget == 100)


@pytest.fixture
def client(seeded_db):
    app = create_app()
    app.config.update(TESTING=True, DATABASE=seeded_db)
    return app.test_client()


def test_carbon_endpoint(client):
    d = client.get("/api/carbon?range=7d").json
    assert d["totals"]["device_kg"] > 0
    assert d["cycle"]["projected_kg_with_recommendations"] <= d["cycle"]["projected_kg"]


def test_recommendations_carry_co2(client):
    d = client.get("/api/recommendations").json
    assert all("co2_saved_kg" in r for r in d["recommendations"])
    assert d["monthly_co2_saved_kg"] > 0
