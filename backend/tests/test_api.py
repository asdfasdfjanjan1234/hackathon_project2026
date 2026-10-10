import pytest

from app import create_app


@pytest.fixture
def client(seeded_db):
    app = create_app()
    app.config.update(TESTING=True, DATABASE=seeded_db)
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


def test_best_time_follows_the_tariff_setting(client):
    client.application.config["ELECTRICITYMAPS_TOKEN"] = ""  # no network in tests
    flat = client.get("/api/best-time?rate=12&current_bill=2500").json
    assert flat["tariff"] == "flat" and flat["shift"] is None and flat["what_if_pop"]["household_kwh_month"] == 208
    assert len(flat["schedule"]) == 24 and len(flat["use"]) == 24
    pop = client.get("/api/best-time?tariff=pop&rate=12&peak_rate=14&offpeak_rate=10").json
    assert pop["tariff"] == "pop" and pop["what_if_pop"] is None
    assert {s["rate"] for s in pop["schedule"]} <= {14.0, 10.0}
    # The seeded readings are at 6 AM, off-peak, so there's nothing to shift.
    assert pop["ai"]["peak_share"] == 0 and pop["shift"] is None and pop["best"]["label"] == "9 PM – 8 AM"


def test_usage_log_breakdowns_add_up_to_the_same_total(client):
    data = client.get("/api/usage/log?range=7d").json
    total = data["total"]
    assert total["wh"] > 0 and data["records"]
    assert set(data["totals"]) == {"date", "ide", "app", "model", "effort"}
    for rows in data["totals"].values():
        assert sum(r["wh"] for r in rows) == pytest.approx(total["wh"])
        assert sum(r["share"] for r in rows) == pytest.approx(1, abs=0.001)
    # Average watts × hours is the energy.
    assert total["avg_watts"] * total["seconds"] / 3600 == pytest.approx(total["wh"], rel=1e-4)
    assert total["kwh"] == pytest.approx(sum(m["kwh"] for m in client.get("/api/usage?range=7d").json["by_model"]), rel=1e-4)


def test_usage_log_records_carry_time_ide_model_and_effort(tmp_path):
    import time
    from app.services import storage

    db = str(tmp_path / "log.db")
    conn = storage.connect(db)
    now = time.time()
    claude = {"app": "Claude Code", "model": "Claude Code · claude-opus-5-5", "kind": "client", "host": "VS Code",
              "effort": "high", "cpu_percent": 20, "rss_mb": 300, "watts": 6.0}
    kiro = {"app": "Kiro", "model": "Kiro · claude-opus-5-5", "kind": "client", "host": None, "effort": None,
            "cpu_percent": 10, "rss_mb": 300, "watts": 3.0}
    for i in range(3):  # three 2-second readings, 6 W and 3 W: 36 J and 18 J
        storage.save_sample(conn, now - 2 * i, 2, 30, 0, 20, None, [claude, kiro])
    conn.close()
    app = create_app()
    app.config.update(TESTING=True, DATABASE=db)
    client = app.test_client()

    data = client.get("/api/usage/log?range=7d&slot=3600").json
    by = {name: {r["key"]: r for r in rows} for name, rows in data["totals"].items()}
    assert by["ide"]["VS Code"]["wh"] == pytest.approx(36 / 3600) and by["ide"]["Kiro"]["wh"] == pytest.approx(18 / 3600)
    assert by["model"]["claude-opus-5-5"]["wh"] == pytest.approx(54 / 3600)  # one model through two apps
    assert by["effort"]["high"]["avg_watts"] == pytest.approx(6.0) and by["effort"][None]["peak_watts"] == 3.0
    record = next(r for r in data["records"] if r["app"] == "Claude Code")
    assert {"start", "end", "ide", "model_name", "effort", "avg_watts", "wh"} <= record.keys()
    assert record["ide"] == "VS Code" and record["model_name"] == "claude-opus-5-5" and record["effort"] == "high"
    assert sum(r["wh"] for r in data["records"]) == pytest.approx(data["total"]["wh"])

    text = client.get("/api/usage/log?range=7d&format=csv").get_data(as_text=True)
    assert text.splitlines()[0].startswith("start,end,ide,app,model_name,effort") and "VS Code" in text
