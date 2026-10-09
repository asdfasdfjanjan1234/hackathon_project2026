"""Applying recommendations to Ollama models."""

import pytest

from app import create_app
from app.services import actions

LOADED = [{"name": "llama3:70b"}]
INSTALLED = [{"name": "llama3:70b"}, {"name": "llama3:8b"}]


def rec(rule, model="Ollama · llama3:70b", **extra):
    return {"rule": rule, "model": model, "scope": "bill", "alternative": False, **extra}


def test_only_loaded_models_can_be_acted_on():
    assert actions.available(rec("idle", model="Ollama · qwen:7b"), LOADED, INSTALLED) is None
    assert actions.available(rec("idle"), LOADED, INSTALLED)["kind"] == "unload"
    assert actions.available(rec("growing", model="llama3:70b"), LOADED, INSTALLED)["model"] == "llama3:70b"


def test_switch_needs_the_smaller_model_installed():
    assert actions.available(rec("smaller", alternative_model="llama3:8b"), LOADED, INSTALLED)["to"] == "llama3:8b"
    assert actions.available(rec("smaller", alternative_model="a 8B model of the same family"), LOADED, INSTALLED) is None


def test_advice_that_cant_be_automated_has_no_action():
    assert actions.available(rec("quantized"), LOADED, INSTALLED) is None
    assert actions.available(rec("cloud", alternative=True), LOADED, INSTALLED) is None
    assert actions.available({**rec("big cloud"), "scope": "datacenter"}, LOADED, INSTALLED) is None


@pytest.fixture
def ollama(monkeypatch):
    calls = []
    monkeypatch.setattr(actions, "ollama_loaded_models", lambda: LOADED)
    monkeypatch.setattr(actions, "ollama_installed_models", lambda: INSTALLED)
    monkeypatch.setattr(actions, "_post", lambda path, body, timeout: calls.append(body) or {})
    monkeypatch.setattr(actions, "SWITCHES", {})
    return calls


def test_apply_switch_unloads_loads_and_records_it(ollama, tmp_path):
    app = create_app()
    app.config.update(TESTING=True, DATABASE=str(tmp_path / "a.db"))
    client = app.test_client()
    res = client.post("/api/actions/apply", json=rec("smaller", alternative_model="llama3:8b"))
    assert res.status_code == 200
    assert {"model": "llama3:70b", "keep_alive": 0} in ollama
    assert client.get("/api/actions/state").json["switches"] == {"llama3:70b": "llama3:8b"}
    assert client.post("/api/actions/apply", json=rec("idle", model="qwen:7b")).status_code == 409
    assert client.post("/api/actions/apply", json={}).status_code == 400


def test_recommendations_say_which_can_be_applied(ollama, tmp_path):
    app = create_app()
    app.config.update(TESTING=True, USE_SAMPLE_DATA=True, DATABASE=str(tmp_path / "a.db"))
    recs = app.test_client().get("/api/recommendations").json["recommendations"]
    applicable = {r["rule"] for r in recs if r["apply"]}
    assert "smaller" in applicable or "idle" in applicable  # John's llama3:70b is "loaded"
    assert all(r["apply"] is None for r in recs if r["rule"] == "quantized")
