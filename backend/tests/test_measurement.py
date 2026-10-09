import time

import pytest

from app import create_app
from app.services import storage
from app.services.ai_processes import classify
from app.services.attribution import PowerModel, attribute, fit_power_model


@pytest.mark.parametrize("name, exe, cmd, expected", [
    ("claude", "/Users/x/.vscode/extensions/anthropic.claude-code-2.1/resources/native-binary/claude", "", "Claude Code"),
    ("Claude", "/Applications/Claude.app/Contents/MacOS/Claude", "", "Claude Desktop"),
    ("Claude Helper (GPU)", "/Applications/Claude.app/Contents/Frameworks/x/Claude Helper (GPU)", "", "Claude Desktop"),
    ("ollama_llama_server", "/usr/local/bin/ollama_llama_server", "", "Ollama"),
    ("co", "/Applications/Visual Studio Code.app/.../@github/copilot-sdk-darwin-arm64/co", "", "GitHub Copilot"),
    # Antigravity bundles VS Code's Copilot runtime; it must not be read as Copilot.
    ("co", "/Applications/Antigravity.app/.../@github/copilot-sdk-darwin-arm64/co", "", "Antigravity"),
    ("language_server_macos_arm",
     "/Applications/Antigravity.app/Contents/Resources/app/extensions/antigravity/bin/language_server_macos_arm", "",
     "Antigravity"),
    ("Antigravity.exe", r"C:\Users\x\AppData\Local\Programs\Antigravity\Antigravity.exe", "", "Antigravity"),
    # Kiro is a VS Code fork too; its bundled Copilot runtime belongs to Kiro.
    ("co", "/Applications/Kiro.app/.../@github/copilot-sdk-darwin-arm64/co", "", "Kiro"),
    ("Kiro.exe", r"C:\Users\x\AppData\Local\Programs\Kiro\Kiro.exe", "", "Kiro"),
    ("node", "/opt/homebrew/bin/node", "node /opt/homebrew/lib/node_modules/@google/gemini-cli/dist/index.js",
     "Gemini CLI"),
    # Devin Desktop (formerly Windsurf) runs its agent as the Devin CLI binary.
    ("Devin Helper (Plugin)", "/Applications/Devin.app/Contents/Frameworks/Devin Helper (Plugin).app/Contents/MacOS/x",
     "", "Devin Desktop"),
    ("language_server_macos_arm",
     "/Applications/Devin.app/Contents/Resources/app/extensions/windsurf/bin/language_server_macos_arm", "",
     "Devin Desktop"),
    ("devin", "/Applications/Devin.app/Contents/Resources/app/extensions/windsurf/devin/bin/devin", "devin acp",
     "Devin"),
    ("devin", "/Users/x/.local/bin/devin", "devin", "Devin"),
])
def test_classify_ai_apps(name, exe, cmd, expected):
    assert classify(name, exe, cmd)[0] == expected


def test_classify_ignores_macos_text_cursor_service():
    exe = "/System/Library/PrivateFrameworks/TextInputUIMacHelper.framework/XPCServices/CursorUIViewService.xpc/Contents/MacOS/CursorUIViewService"
    assert classify("CursorUIViewService", exe, "") is None


def test_fit_recovers_machine_coefficients():
    windows = [(4.0 + 0.2 * cpu + 0.1 * gpu, cpu, gpu) for cpu, gpu in
               [(5, 0), (20, 10), (40, 5), (60, 50), (10, 30), (80, 20), (30, 70), (50, 40), (15, 60)]]
    m = fit_power_model(windows)
    assert m.idle_watts == pytest.approx(4.0)
    assert m.watts_per_cpu_pct == pytest.approx(0.2)
    assert m.watts_per_gpu_pct == pytest.approx(0.1)
    assert m.fitted_on == 9


def test_fit_needs_enough_varied_readings():
    assert fit_power_model([(5.0, 10, 0)] * 3) is None   # too few
    assert fit_power_model([(5.0, 10, 0)] * 20) is None  # CPU never changed


def test_attribution_excludes_idle_and_gives_gpu_to_local_models():
    model = PowerModel(idle_watts=3, watts_per_cpu_pct=0.2, watts_per_gpu_pct=0.1)
    apps = [
        {"app": "Ollama", "kind": "local", "cpu_percent": 400.0},      # 4 of 8 cores
        {"app": "Claude Code", "kind": "client", "cpu_percent": 16.0},
    ]
    attribute(model, gpu_pct=50, apps=apps, ncpu=8)
    assert apps[0]["watts"] == pytest.approx(0.2 * 50 + 0.1 * 50)  # CPU share + all GPU power
    assert apps[1]["watts"] == pytest.approx(0.2 * 2)               # CPU share only


def test_stored_samples_become_daily_kwh(tmp_path):
    conn = storage.connect(str(tmp_path / "t.db"))
    app = {"app": "Ollama", "model": "Ollama · llama3:8b", "kind": "local", "cpu_percent": 100, "rss_mb": 5000}
    for i in range(10):  # 10 samples × 360 s × 100 W = 100 Wh
        storage.save_sample(conn, time.time() - i, 360, 50, 20, 30, None, [{**app, "watts": 100}])
    (row,) = storage.daily_usage(conn)
    assert row["model"] == "Ollama · llama3:8b"
    assert row["kwh"] == pytest.approx(0.1)
    assert row["source"] == "measured"


def test_dashboard_uses_collected_data(tmp_path):
    db = str(tmp_path / "t.db")
    conn = storage.connect(db)
    app = {"app": "Claude Code", "model": None, "kind": "client", "cpu_percent": 20, "rss_mb": 300, "watts": 2.0}
    storage.save_sample(conn, time.time(), 3600, 30, 10, 8, 7.5, [app])

    flask_app = create_app()
    flask_app.config.update(TESTING=True, USE_SAMPLE_DATA=False, DATABASE=db)
    client = flask_app.test_client()

    usage = client.get("/api/usage").json
    assert usage["by_model"][0]["model"] == "Claude Code"
    assert usage["by_model"][0]["kwh"] == pytest.approx(0.002)
    live = client.get("/api/live").json
    assert live["source"] == "collector" and live["apps"][0]["name"] == "Claude Code"
    assert client.get("/api/impact").json["local_ai_kwh"] == pytest.approx(0.002, abs=0.01)


def test_formula_cpu_watts_give_their_memory_part_to_memory():
    model = PowerModel(idle_watts=3, watts_per_cpu_pct=0.2, watts_per_gpu_pct=0.1)
    apps = [{"app": "Ollama", "kind": "local", "cpu_percent": 400.0}]  # 4 of 8 cores, 50 % of the CPU
    attribute(model, gpu_pct=0, apps=apps, ncpu=8, cpu_pct=50, memory_est=2.0)
    (a,) = apps
    assert a["memory_watts"] == pytest.approx(2.0)          # all the compute, so all the memory traffic
    assert a["cpu_watts"] == pytest.approx(0.2 * 50 - 2.0)  # moved out of the CPU formula
    assert a["watts"] == pytest.approx(0.2 * 50)            # total unchanged
    assert a["cpu_watts"] + a["gpu_watts"] + a["memory_watts"] == pytest.approx(a["watts"])


def test_measured_parts_are_kept_separate():
    model = PowerModel()
    apps = [{"app": "Ollama", "kind": "local", "cpu_percent": 100.0, "pids": [1]},
            {"app": "Claude Code", "kind": "client", "cpu_percent": 100.0, "pids": [2]}]
    # 2 of 4 busy cores in each app; the GPU is all Ollama's.
    attribute(model, 80, apps, ncpu=4, cpu_pct=50, measured={"cpu": 20.0, "gpu": 30.0, "memory": 5.0},
              gpu_pids={1})
    ollama, claude = apps
    assert ollama["cpu_watts"] == pytest.approx(10.0) and claude["cpu_watts"] == pytest.approx(10.0)
    assert ollama["gpu_watts"] == pytest.approx(30.0) and ollama["gpu_share"] == 1.0
    assert claude["gpu_watts"] == 0.0
    # Memory follows compute: Ollama did 40 of the 50 W of CPU+GPU work.
    assert ollama["memory_watts"] == pytest.approx(4.0) and claude["memory_watts"] == pytest.approx(1.0)
    assert ollama["watts"] == pytest.approx(44.0)


def test_loaded_model_that_is_not_generating_gets_no_memory_power():
    apps = [{"app": "Ollama", "kind": "local", "cpu_percent": 0.0, "rss_mb": 40_000}]
    attribute(PowerModel(), 0, apps, ncpu=8, cpu_pct=10, measured={"memory": 3.0})
    assert apps[0]["memory_watts"] == 0.0 and apps[0]["watts"] == 0.0
