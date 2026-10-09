from datetime import date, timedelta

import pytest

from app.services.forecasting import forecast_bill
from app.services.recommendations import build_recommendations, reductions

TODAY = date(2026, 10, 9)
GB = 1e9


def daily(model, kwh, days=14, kind="local", active_hours=None):
    return [{"date": (TODAY - timedelta(days=i)).isoformat(), "model": model, "kwh": kwh, "kind": kind,
             "source": "measured", "active_hours": active_hours} for i in range(days, 0, -1)]


def recommend(rows, signals=None, budget=100_000, rate=12, baseline=1500):
    f = forecast_bill(rows, rate=rate, baseline_bill=baseline, today=TODAY, budget=budget)
    return build_recommendations(rows, f, rate, budget, signals or {}, today=TODAY), f


def by_rule(recs):
    return {r["rule"]: r for r in recs}


def installed(name, family, params_b, quantization, size_gb):
    return {"app": "Ollama", "name": name, "family": family, "params_b": params_b,
            "quantization": quantization, "size_bytes": size_gb * GB}


def test_switch_to_a_smaller_installed_model_of_the_same_family_on_a_real_device():
    signals = {"installed": [installed("qwen2.5:32b", "qwen2", 32, "Q4_K_M", 19.9),
                             installed("qwen2.5:7b", "qwen2", 7, "Q4_K_M", 4.7),
                             installed("llama3:8b", "llama", 8, "Q4_0", 4.7)]}
    recs, _ = recommend(daily("Ollama · qwen2.5:32b", 2.0), signals)
    rec = by_rule(recs)["smaller"]
    assert rec["alternative_model"] == "qwen2.5:7b"  # same family, not llama3
    assert "4.2×" in rec["message"]
    assert rec["monthly_savings"] == pytest.approx(2.0 * 31 * 12 * 0.5 * (1 - 4.7 / 19.9), rel=0.01)


def test_8_bit_models_get_the_quantized_recommendation_and_4_bit_ones_dont():
    signals = {"installed": [installed("llama3:8b-q8_0", "llama", 8, "Q8_0", 8.5),
                             installed("llama3:8b", "llama", 8, "Q4_K_M", 4.9)]}
    recs, _ = recommend(daily("Ollama · llama3:8b-q8_0", 1.0) + daily("Ollama · llama3:8b", 1.0), signals)
    quantized = [r for r in recs if r["rule"] == "quantized"]
    assert [r["model"] for r in quantized] == ["Ollama · llama3:8b-q8_0"]
    assert "44% less energy per token" in quantized[0]["message"]


def test_idle_loaded_model_uses_its_measured_idle_energy():
    signals = {"idle_loaded": [{"model": "Ollama · llama3:8b", "idle_hours": 20, "kwh": 0.07, "rss_mb": 5000,
                                "days": 7}]}
    rec = by_rule(recommend(daily("Ollama · llama3:8b", 0.5), signals)[0])["idle"]
    assert rec["monthly_savings"] == pytest.approx(0.07 * 12 * 30 / 7, rel=0.01)
    assert "OLLAMA_KEEP_ALIVE" in rec["message"] and "20 idle hours" in rec["message"]


def test_tool_runs_that_outweigh_the_agent():
    rows = daily("Claude Code · tool runs", 0.02, kind="client") + daily("Claude Code · claude-opus-5-5", 0.005,
                                                                         kind="client")
    rec = by_rule(recommend(rows)[0])["tool runs"]
    assert rec["model"] == "Claude Code · tool runs" and "affected tests" in rec["message"]


def test_costliest_model_per_hour_of_use():
    rows = daily("sdxl-turbo", 2.2, active_hours=10) + daily("llama3:8b", 0.75, active_hours=10)
    rec = by_rule(recommend(rows)[0])["per hour"]
    assert rec["action"] == "STOP" and rec["model"] == "sdxl-turbo"
    assert "₱2.64 per hour" in rec["message"]


def test_cloud_model_switch_is_data_center_energy_not_on_the_bill():
    hint = {"share": 0.9, "models": ["Opus 5.5"], "wh_saved": 120.0, "message": "90% went to Opus 5.5."}
    rec = by_rule(recommend(daily("Claude Code · claude-opus-5-5", 0.001, kind="client"), {"cloud": hint})[0])[
        "big cloud"]
    assert rec["scope"] == "datacenter" and rec["monthly_savings"] == 0 and rec["wh_saved"] == 120.0


def test_heavy_local_use_offers_cloud_as_an_alternative_left_out_of_the_forecast():
    recs, f = recommend(daily("llama3:70b", 3.0))
    rec = by_rule(recs)["cloud"]
    assert rec["alternative"]
    assert "llama3:70b" not in reductions([rec], f)


def test_budget_rule_counts_the_other_recommendations_first():
    recs, f = recommend(daily("llama3:70b", 3.0), budget=1900)
    budget = recs[0]
    assert budget["rule"] == "budget" and "Oct" in budget["message"]
    saved = reductions(recs, f)
    with_recs = forecast_bill(daily("llama3:70b", 3.0), rate=12, baseline_bill=1500, today=TODAY, budget=1900,
                              reductions=saved)
    assert with_recs["forecast_bill_with_recommendations"] == pytest.approx(1900, abs=1)


def test_budget_that_ai_cuts_cannot_meet_says_so():
    recs, _ = recommend(daily("llama3:8b", 0.1), budget=1400)  # the baseline alone is ₱1,500
    assert recs[0]["rule"] == "budget" and "non-AI use" in recs[0]["message"]


def test_recommendations_on_the_same_model_compound():
    f = {"by_model": [{"model": "m", "monthly_cost": 100.0}]}
    recs = [{"model": "m", "monthly_savings": 50.0, "scope": "bill", "alternative": False},
            {"model": "m", "monthly_savings": 50.0, "scope": "bill", "alternative": False}]
    assert reductions(recs, f) == {"m": pytest.approx(0.75)}
