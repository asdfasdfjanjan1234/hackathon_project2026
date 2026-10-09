import json
import sqlite3
import time
from datetime import date

import pytest

from app import create_app
from app.services import device_reader, model_usage
from app.services import ai_processes
from app.services.ai_processes import app_name, group_processes, label_active_models, unrecognized_apps
from app.services.forecasting import forecast_bill
from app.services.models_catalog import REFERENCE, cloud_model, datacenter_wh, provider_of, relative_energy

VSCODE = "/Applications/Visual Studio Code.app/Contents/MacOS/Code"
EXTHOST = "/Applications/Visual Studio Code.app/Contents/Frameworks/Code Helper (Plugin).app/Contents/MacOS/Code Helper (Plugin)"
CLAUDE = "/Users/x/.vscode/extensions/anthropic.claude-code-2.1-darwin-arm64/resources/native-binary/claude"


def proc(ppid, name, exe="", cmdline=""):
    return {"ppid": ppid, "name": name, "exe": exe, "cmdline": cmdline}


def test_agent_children_are_tool_runs_and_host_is_found():
    procs = {
        1: proc(0, "launchd"),
        10: proc(1, "Code", VSCODE),
        11: proc(10, "Code Helper (Plugin)", EXTHOST),
        12: proc(11, "claude", CLAUDE),
        13: proc(12, "zsh", "/bin/zsh"),
        14: proc(13, "node", "/usr/local/bin/node", "node npm test"),
        20: proc(1, "Terminal", "/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal"),
        21: proc(20, "zsh", "/bin/zsh"),
        22: proc(21, "claude", "/usr/local/bin/claude"),
        30: proc(11, "codex", "/Users/x/.vscode/extensions/openai.chatgpt-1.0/bin/macos-aarch64/codex"),
    }
    groups = group_processes(procs)
    assert groups[12] == ("Claude Code", "client", "VS Code", False)
    assert groups[14] == ("Claude Code", "client", "VS Code", True)
    assert groups[22] == ("Claude Code", "client", "Terminal", False)
    assert groups[30] == ("Codex", "client", "VS Code", False)
    assert 21 not in groups and 11 not in groups  # the user's shell and VS Code itself aren't AI


def test_agents_inside_antigravity_have_it_as_host():
    app = "/Applications/Antigravity.app/Contents"
    procs = {
        1: proc(0, "launchd"),
        10: proc(1, "Electron", f"{app}/MacOS/Electron"),
        11: proc(10, "Antigravity Helper (Plugin)", f"{app}/Frameworks/Antigravity Helper (Plugin).app/Contents/MacOS/x"),
        12: proc(11, "claude", "/Users/x/.antigravity/extensions/anthropic.claude-code-2.1/resources/native-binary/claude"),
    }
    groups = group_processes(procs)
    assert groups[11][0] == "Antigravity"
    assert groups[12] == ("Claude Code", "client", "Antigravity", False)


def test_own_process_is_not_counted_as_a_tool_run():
    procs = {1: proc(0, "claude", "/usr/local/bin/claude"), 2: proc(1, "python", "/usr/bin/python3"),
             3: proc(2, "powermetrics", "/usr/bin/powermetrics")}
    assert set(group_processes(procs, exclude={2})) == {1}


def test_client_apps_are_labeled_with_their_active_model():
    apps = [{"app": "Claude Code", "kind": "client", "model": None},
            {"app": "Claude Code", "kind": "client", "model": "Claude Code · tool runs"},
            {"app": "Ollama", "kind": "local", "model": None}]
    label_active_models(apps, {"Claude Code": "claude-opus-5-5", "Ollama": "x"})
    assert [a["model"] for a in apps] == ["Claude Code · claude-opus-5-5", "Claude Code · tool runs", None]


@pytest.fixture
def fresh_scan():
    ai_processes._seen.clear()
    ai_processes._scan["at"] = None
    yield
    ai_processes._seen.clear()
    ai_processes._scan["at"] = None


ZED = "/Applications/Zed.app/Contents/MacOS"
FW_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python"


def test_unknown_apps_talking_to_an_ai_api_are_counted(fresh_scan):
    procs = {
        1: proc(0, "launchd"),
        10: proc(1, "zed", f"{ZED}/zed"),
        11: proc(10, "zed-helper", f"{ZED}/zed-helper"),  # same bundle: counted with it
        20: proc(1, "Python", FW_PYTHON, "python /usr/local/bin/aider"),
        21: proc(1, "Python", FW_PYTHON, "python manage.py runserver"),  # same program, no AI traffic
        30: proc(1, "Google Chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        40: proc(1, "Code", VSCODE),
        41: proc(40, "Code Helper (Plugin)", EXTHOST),  # e.g. Cline: shares VS Code's extension host
        50: proc(1, "claude", "/usr/local/bin/claude"),
        51: proc(50, "curl", "/usr/bin/curl"),  # Claude Code's tool run, not a new app
        60: proc(1, "nsurlsessiond", "/usr/libexec/nsurlsessiond"),
    }
    for p in procs.values():
        p["argv"] = p["cmdline"].split()
    talking = {10, 20, 30, 41, 51, 60}
    found = unrecognized_apps(procs, talking.__contains__, now=0)
    assert found == {10: ("Zed", "client"), 11: ("Zed", "client"), 20: ("aider", "client")}

    groups = group_processes(procs, extra=found)
    assert groups[10] == ("Zed", "client", None, False)
    assert groups[51] == ("Claude Code", "client", None, True)


def test_unknown_apps_stay_counted_between_requests(fresh_scan):
    procs = {1: proc(0, "launchd"), 10: proc(1, "zed", f"{ZED}/zed")}
    assert unrecognized_apps(procs, lambda pid: True, now=0)
    # No connection now and no scan due: still counted, until STICKY_S after the last one.
    assert unrecognized_apps(procs, lambda pid: False, now=ai_processes.SCAN_EVERY_S - 1)
    assert unrecognized_apps(procs, lambda pid: False, now=ai_processes.STICKY_S - 1)
    assert unrecognized_apps(procs, lambda pid: False, now=ai_processes.STICKY_S) == {}


@pytest.mark.parametrize("name, exe, argv, expected", [
    ("zed", f"{ZED}/zed", [], "Zed"),
    ("Trae Helper (Plugin)", "/Applications/Trae.app/Contents/Frameworks/Trae Helper (Plugin).app/Contents/MacOS/x",
     [], "Trae"),
    ("Python", FW_PYTHON, ["python", "-u", "/usr/local/bin/aider"], "aider"),
    ("node", "/opt/homebrew/bin/node", ["node", "/opt/homebrew/lib/node_modules/@acme/agent/dist/index.js"],
     "@acme/agent"),
    ("goose.exe", r"C:\Users\x\goose.exe", [], "goose"),
])
def test_unrecognized_app_names(name, exe, argv, expected):
    assert app_name(name, exe, argv) == expected


def _assistant(msg_id, model, out, ts="2026-10-09T10:00:00Z", **usage):
    return json.dumps({"type": "assistant", "requestId": "r" + msg_id, "timestamp": ts, "message": {
        "id": msg_id, "model": model, "content": [{"type": "text", "text": "secret code"}],
        "usage": {"input_tokens": 10, "output_tokens": out, "cache_read_input_tokens": 1000,
                  "cache_creation_input_tokens": 300, "cache_creation": {"ephemeral_1h_input_tokens": 100},
                  **usage}}})


def test_claude_code_responses_are_counted_once():
    lines = [_assistant("a", "claude-opus-5-5", 50), _assistant("a", "claude-opus-5-5", 50),  # two content blocks
             _assistant("b", "claude-sonnet-5-5", 20), _assistant("c", "<synthetic>", 0),
             json.dumps({"type": "user", "message": {"content": "hi"}})]
    parsed = model_usage.parse_claude_code(lines)
    assert len(parsed) == 2
    _, model, tokens = parsed[("a", "ra")]
    assert model == "claude-opus-5-5"
    assert tokens == {"input": 10, "output": 50, "cache_read": 1000, "cache_write_5m": 200, "cache_write_1h": 100}
    assert "secret" not in repr(parsed)


def test_codex_tokens_are_deltas_of_cumulative_totals():
    def count(ts, inp, cached, out):
        return json.dumps({"timestamp": ts, "type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out}}}})
    lines = [json.dumps({"type": "turn_context", "payload": {"model": "gpt-5.5"}}),
             count("2026-10-09T01:00:00Z", 100, 40, 10),
             count("2026-10-09T01:00:01Z", 100, 40, 10),  # repeated total: no new tokens
             count("2026-10-09T01:01:00Z", 250, 140, 30)]
    tokens = [t for _, _, t in model_usage.parse_codex(lines).values()]
    assert tokens == [{"input": 60, "output": 10, "cache_read": 40}, {"input": 50, "output": 20, "cache_read": 100}]


def test_copilot_counts_successful_requests():
    lines = ["2026-10-06 09:34:25.905 [info] ccreq:07.copilotmd | success | gpt-4o-mini-2024-07-18 | 662ms | [x]",
             "2026-10-06 09:35:06.175 [info] ccreq:f5.copilotmd | failed | gpt-5.3-codex | 248ms | [y]"]
    assert list(model_usage.parse_copilot(lines).values()) == [("2026-10-06", "gpt-4o-mini-2024-07-18", {})]


def test_copilot_requests_in_different_log_files_are_all_counted(tmp_path):
    today = date.today().isoformat()
    for i, req in enumerate(["ccreq:aa.copilotmd", "ccreq:bb.copilotmd"]):
        (tmp_path / f"{i}.log").write_text(f"{today} 09:00:00.000 [info] {req} | success | gpt-4o | 1ms | [x]\n")
    source = ("GitHub Copilot", lambda: [str(tmp_path / "*.log")], model_usage.parse_copilot)
    assert len(model_usage.scan_events(sources=[source])) == 2


def test_opencode_reads_tokens_from_its_database(tmp_path):
    db = tmp_path / "opencode.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE message (id text, data text)")
        conn.executemany("INSERT INTO message VALUES (?, ?)", [
            ("m1", json.dumps({"role": "user", "time": {"created": 1789529000000}})),
            ("m2", json.dumps({"role": "assistant", "modelID": "claude-sonnet-5-5", "time": {"created": 1789529012575},
                               "tokens": {"input": 537, "output": 391, "reasoning": 9,
                                          "cache": {"read": 142193, "write": 10}}})),
            ("m3", json.dumps({"role": "assistant", "modelID": "claude-sonnet-5-5", "time": {"created": 1789529012575},
                               "tokens": {"input": 0, "output": 0, "cache": {}}})),  # aborted: nothing used
        ])
    conn.close()
    parsed = model_usage._parse_file(str(db), model_usage.parse_opencode)
    assert list(parsed) == [("m2",)]
    _, model, tokens = parsed[("m2",)]
    assert model == "claude-sonnet-5-5"
    assert tokens == {"input": 537, "output": 400, "cache_read": 142193, "cache_write_5m": 10}


def test_gemini_cli_tokens_exclude_cached_input():
    session = {"messages": [
        {"id": "u", "type": "user", "timestamp": "2026-10-09T10:00:00Z", "content": "secret code"},
        {"id": "g", "type": "gemini", "timestamp": "2026-10-09T10:00:05Z", "content": "secret answer",
         "model": "gemini-2.5-flash", "tokens": {"input": 1000, "output": 50, "cached": 600, "thoughts": 25}}]}
    parsed = model_usage.parse_gemini(json.dumps(session, indent=1).splitlines(True))
    assert [(m, t) for _, m, t in parsed.values()] == [
        ("gemini-2.5-flash", {"input": 400, "output": 75, "cache_read": 600})]
    assert "secret" not in repr(parsed)


def test_kiro_counts_agent_requests_but_not_its_router():
    log = "2026-06-30 16:26:{} [info] [q-developer-converse] Sending GenerateAssistantResponse modelId={} agentMode={} origin=AI_EDITOR"
    lines = [log.format("33.951", "simple-task", "intent-classification"),
             log.format("33.994", "claude-sonnet-4.5", "vibe"),
             log.format("39.060", "claude-sonnet-4.5", "vibe"),
             "2026-06-30 16:26:40.000 [info] [q-developer-converse] Received response"]
    assert list(model_usage.parse_kiro(lines).values()) == [("2026-06-30", "claude-sonnet-4.5", {})] * 2


def test_amazon_q_counts_answers_per_tab_model():
    def tab(tab_id, model, *types):
        msgs = [{"type": t, "body": "secret", "timestamp": f"2026-07-01T10:00:0{i}Z"} for i, t in enumerate(types)]
        return {"historyId": tab_id, **({"modelId": model} if model else {}), "conversations": [{"messages": msgs}]}
    history = {"collections": [{"data": [tab("a", "claude-sonnet-4.5", "prompt", "answer", "prompt", "answer"),
                                         tab("b", None, "prompt", "answer")]}]}
    parsed = model_usage.parse_amazon_q([json.dumps(history)])
    assert sorted(m for _, m, _ in parsed.values()) == ["claude-sonnet-4.5", "claude-sonnet-4.5", "default"]
    assert "secret" not in repr(parsed)


def test_datacenter_estimate_matches_reference_query():
    typical = {"output": REFERENCE["output_tokens"]}
    assert datacenter_wh("claude-sonnet-5-5", typical) == pytest.approx(REFERENCE["wh_per_query"])
    assert datacenter_wh("claude-opus-5-5", typical) == pytest.approx(2 * REFERENCE["wh_per_query"])
    assert relative_energy("claude-haiku-4-5-20251001") == 0.5  # dated ids match their model
    assert datacenter_wh("gpt-4o-mini", typical) is None  # no price in the catalog: no estimate


@pytest.mark.parametrize("model_id, priced_as, approximate", [
    ("claude-opus-5-5", "Opus 5.5", False),
    ("claude-opus-5-5-20261001", "Opus 5.5", False),
    ("claude-haiku-4-5@20251001", "Haiku 4.5", False),
    # A new version isn't read as an older one with the same prefix (claude-opus-5).
    ("claude-opus-5-6", "Opus 5.5", True),
    ("claude-opus-6", "Opus 5.5", True),
    ("claude-sonnet-4.5", "Sonnet 5.5", True),
    ("claude-3-5-sonnet-20241022", "Sonnet 5.5", True),
    ("us.anthropic.claude-haiku-4-5-20251001-v1:0", "Haiku 4.5", True),
    ("CLAUDE_SONNET_4_20250514_V1_0", "Sonnet 5.5", True),
])
def test_unknown_claude_models_are_priced_by_family(model_id, priced_as, approximate):
    m = cloud_model(model_id)
    assert (m["name"], m["approximate"]) == (priced_as, approximate)


def test_models_outside_the_catalog():
    assert cloud_model("gpt-6") is None and cloud_model("sonnet-poetry-7b") is None
    assert [provider_of(m) for m in ("gpt-5-codex", "o4-mini", "gemini-3-pro", "claude-opus-6", "default")] == \
        ["OpenAI", "OpenAI", "Google", "Anthropic", None]
    models, _ = model_usage.summarize([("Claude Code", "2026-10-09", "claude-opus-6", {"output": 500}),
                                       ("Codex", "2026-10-09", "gpt-6", {"output": 500})])
    by_id = {m["model"]: m for m in models}
    assert by_id["claude-opus-6"]["name"] == "claude-opus-6"  # not shown as Opus 5.5
    assert by_id["claude-opus-6"]["priced_as"] == "Opus 5.5" and by_id["claude-opus-6"]["datacenter_wh"]
    assert by_id["gpt-6"]["provider"] == "OpenAI" and by_id["gpt-6"]["datacenter_wh"] is None


def test_summary_and_switch_hint():
    events = [("Claude Code", "2026-10-09", "claude-opus-5-5", {"output": 1000}),
              ("Claude Code", "2026-10-09", "claude-opus-5-5", {"output": 1000}),
              ("Claude Code", "2026-10-08", "claude-sonnet-5-5", {"output": 100})]
    models, daily = model_usage.summarize(events)
    assert models[0]["model"] == "claude-opus-5-5" and models[0]["requests"] == 2
    assert [d["date"] for d in daily] == ["2026-10-08", "2026-10-09"]
    hint = model_usage.switch_hint(models)
    assert hint["share"] > 0.9 and hint["wh_saved"] > 0


def test_installed_extensions(tmp_path):
    for name in ["anthropic.claude-code-2.1.289-darwin-arm64", "kodu-ai.claude-dev-experimental-1.0.0",
                 "ms-python.python-2026.1.0"]:
        (tmp_path / name).mkdir()
    found = {e["id"]: e["measurable"] for e in model_usage.installed_extensions(str(tmp_path))}
    assert found == {"anthropic.claude-code": True, "kodu-ai.claude-dev-experimental": False}


def test_forecast_leaves_cloud_energy_off_the_bill():
    daily = [{"date": "2026-10-01", "model": "llama3:8b", "kwh": 1.0, "source": "measured"},
             {"date": "2026-10-01", "model": "claude", "kwh": 50.0, "source": "estimated"}]
    f = forecast_bill(daily, rate=10, baseline_bill=1000)
    assert [m["model"] for m in f["by_model"]] == ["llama3:8b"]


class FakeCollector:
    def __init__(self, conn, interval, sensors=None):
        from app.services.attribution import PowerModel
        self.model = PowerModel()

    def step(self):
        return {"ts": time.time(), "cpu": 10.0, "gpu": 0.0, "est_watts": 5.0, "measured_watts": 4.5,
                "components": {}, "apps": [{"app": "Claude Code", "watts": 0.1}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(device_reader, "Collector", FakeCollector)
    monkeypatch.setattr(device_reader, "reader", device_reader.DeviceReader())
    from app.routes import device
    monkeypatch.setattr(device, "reader", device_reader.reader)
    app = create_app()
    app.config.update(TESTING=True, USE_SAMPLE_DATA=True, DATABASE=str(tmp_path / "test.db"))
    return app.test_client()


def test_start_reading_switches_to_device_data(client):
    assert client.get("/api/usage").json["data_source"] == "sample"
    started = client.post("/api/device/start").json
    assert started["started"] and started["running"] and started["data_source"] == "device"
    assert started["system"]["os"] and "gpu" in started["sensors"]
    assert client.post("/api/device/start").json["started"] is False  # already running
    for _ in range(50):
        if client.get("/api/device/status").json["samples"]:
            break
        time.sleep(0.1)
    status = client.post("/api/device/stop").json
    assert not status["running"]
    assert client.get("/api/usage").json["data_source"] == "device"
    assert client.post("/api/device/source", json={"source": "sample"}).json["data_source"] == "sample"
    assert client.post("/api/device/source", json={"source": "x"}).status_code == 400


def test_bill_params_come_from_the_query(client):
    d = client.get("/api/impact?rate=12&baseline_rate=12&baseline_bill=1000&current_bill=1000").json
    assert d["increase"] == 0 and d["verdict"] == "no_increase"


def test_models_endpoint(client, monkeypatch):
    monkeypatch.setattr(model_usage, "scan_events", lambda days=30: [
        ("Claude Code", "2026-10-09", "claude-opus-5-5", {"output": 500})])
    d = client.get("/api/models").json
    assert d["models"][0]["datacenter_wh"] == pytest.approx(0.6)
    assert d["models"][0]["device_kwh"] is None and d["reference"]["source"]
