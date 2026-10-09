import json
import time
from datetime import date, timedelta

import pytest

from app import create_app
from app.services import arima_forecast, storage
from app.services.forecasting import forecast_bill
from app.services.usage_store import this_machine_id

TODAY = date(2026, 10, 9)
PARAMS = {"rate": 10.0, "baseline_bill": 1000.0, "cycle_start_day": 1, "tariff": "flat", "peak_rate": 0.0,
          "offpeak_rate": 0.0, "budget": 2000.0}


def rows(model, values, end):
    start = end - timedelta(days=len(values) - 1)
    return [{"date": (start + timedelta(days=i)).isoformat(), "model": model, "kwh": v, "kind": "local",
             "source": "measured"} for i, v in enumerate(values)]


@pytest.fixture(autouse=True)
def fresh_cache():
    arima_forecast._cache.clear()


def test_the_days_ahead_replace_the_trend_for_the_rest_of_the_cycle():
    # Trend: 1 kWh a day; ARIMA: 2 kWh a day from tomorrow, and 0.5 kWh more today on top of the 1 measured.
    daily = rows("llama3:8b", [1.0] * 9, TODAY)
    days = {TODAY: 0.5, **{TODAY + timedelta(days=i): 2.0 for i in range(1, 23)}}
    f = forecast_bill(daily, rate=10, baseline_bill=1000, today=TODAY, reductions={"llama3:8b": 0.25},
                      ahead={"days": days, "low": 0.5, "high": 2.0})
    to_come = (0.5 + 22 * 2.0) * 10
    assert f["ai_cost"] == pytest.approx(8 * 10 + 1.5 * 10 + 22 * 20)
    assert f["daily"][-1]["bill_to_date"] == pytest.approx(f["forecast_bill"])
    assert f["daily"][8]["ai_kwh"] == pytest.approx(1.5)  # today: measured + the rest of the day
    # The recommendations save their share (25%) of each day after today.
    assert f["forecast_bill_with_recommendations"] == pytest.approx(f["forecast_bill"] - 22 * 20 * 0.25)
    assert f["forecast_range"] == {"low": pytest.approx(f["forecast_bill"] - to_come * 0.5),
                                   "high": pytest.approx(f["forecast_bill"] + to_come)}
    assert sum(m["monthly_cost"] for m in f["by_model"]) == pytest.approx(f["ai_cost"])
    assert f["by_model"][0]["remaining_cost"] == pytest.approx(22 * 20)


def test_without_the_days_ahead_its_the_trend():
    f = forecast_bill(rows("llama3:8b", [1.0] * 9, TODAY - timedelta(days=1)), rate=10, baseline_bill=1000, today=TODAY)
    assert f["forecast_bill"] == pytest.approx(1000 + 31 * 10) and f["forecast_range"] is None


def write_model(folder, device_id, beats_baselines=True):
    """A model file as 05_finetune_device.py saves it: one ARIMA(1,0,1) for "Other AI apps"."""
    model = {"spec": {"order": [1, 0, 1], "seasonal_order": [0, 0, 0, 0], "label": "ARIMA(1,0,1)"},
             "params": {"ar.L1": 0.5, "ma.L1": 0.1, "sigma2": 0.5}, "mean": 0.5, "std": 1.0,
             "routine": [[0.0] * 24 for _ in range(7)], "exog": [], "trained": {}}
    saved = {"created": "2026-10-10T00:00:00", "device_id": device_id, "step_minutes": 15,
             "agents": {"Other AI apps": {"model": model, "chosen": {"spec": "ARIMA(1,0,1)", "start": "warm"}}},
             "total": {"arima_by_agent": {"window_total_error": 0.2}}, "beats_baselines": beats_baselines,
             "horizon_hours": 2.0, "coverage": {"known_hours": 48.0, "days": 2, "hours_of_day": 24},
             "thresholds_w": {"active_w": 1.0, "light_max_w": None, "moderate_max_w": None}}
    (folder / f"device_{device_id}_model.json").write_text(json.dumps(saved))


def cfg(folder, mode="auto"):
    return {"ARIMA_MODEL_DIR": str(folder), "ARIMA_FORECAST": mode}


def test_it_says_why_the_trend_is_used(tmp_path):
    assert arima_forecast.arima_ahead(None, 3, PARAMS, cfg(tmp_path, "off"))[1]["reason"].startswith("ARIMA is turned off")
    assert arima_forecast.arima_ahead(None, None, PARAMS, cfg(tmp_path))[1]["reason"] == "No readings from this device yet"
    assert "No fine-tuned ARIMA model" in arima_forecast.arima_ahead(None, 3, PARAMS, cfg(tmp_path))[1]["reason"]
    write_model(tmp_path, 3, beats_baselines=False)
    ahead, method = arima_forecast.arima_ahead(None, 3, PARAMS, cfg(tmp_path))
    assert ahead is None and method["name"] == "trend" and "didn't beat simple baselines" in method["reason"]
    assert method["arima"]["models"] == {"Other AI apps": "ARIMA(1,0,1)"}


def seed_device(db, days=2):
    """This computer's readings in 15-minute steps through now: an Ollama model at 40 W in the daytime."""
    conn = storage.connect(db)
    device = storage.register_device(conn, {"machine_id": this_machine_id()})
    now = time.time()
    for i in range(days * 96, 0, -1):
        ts = now - i * 900
        watts = 40 if 9 <= time.localtime(ts).tm_hour < 18 else 0.5
        app = {"app": "Ollama", "model": "Ollama · llama3:8b", "kind": "local", "cpu_percent": 50, "rss_mb": 4000,
               "watts": watts}
        storage.save_sample(conn, ts, 900, 20, 0, 30, None, [app], device_id=device)
    conn.close()
    return device


@pytest.mark.parametrize("mode, beats, used", [("auto", True, True), ("auto", False, False), ("on", False, True)])
def test_forecast_endpoint_runs_the_fine_tuned_model(tmp_path, mode, beats, used):
    pytest.importorskip("statsmodels")
    db = str(tmp_path / "test.db")
    write_model(tmp_path, seed_device(db), beats_baselines=beats)
    app = create_app()
    app.config.update(TESTING=True, DATABASE=db, ARIMA_MODEL_DIR=str(tmp_path), ARIMA_FORECAST=mode)
    f = app.test_client().get("/api/forecast").json
    assert f["method"]["name"] == ("arima" if used else "trend")
    assert f["daily"][-1]["bill_to_date"] == pytest.approx(f["forecast_bill"], abs=0.05)
    if used:
        assert f["forecast_range"]["low"] <= f["forecast_bill"] <= f["forecast_range"]["high"]
        assert f["method"]["interval"] == 0.8
    else:
        assert f["forecast_range"] is None
