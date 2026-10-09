import json
import time

import pytest

from app.services import local_models, sensors_linux, storage
from app.services.ai_processes import flag_value
from app.services.attribution import PowerModel, attribute, default_power_model
from app.services.measurement import parse_nvidia_compute_pids, parse_nvidia_gpus
from app.services.sensors_windows import gpu_engine_usage
from app.services.system_info import linux_devices, parse_lspci


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text))
    return path


# --- Linux ------------------------------------------------------------------

def test_linux_battery_power_only_while_discharging(tmp_path):
    bat = "sys/class/power_supply/BAT0"
    write(tmp_path, f"{bat}/type", "Battery")
    write(tmp_path, f"{bat}/status", "Discharging")
    write(tmp_path, f"{bat}/current_now", 1_000_000)   # 1 A
    write(tmp_path, f"{bat}/voltage_now", 12_000_000)  # 12 V
    write(tmp_path, "sys/class/power_supply/AC/type", "Mains")
    assert sensors_linux.battery_watts(str(tmp_path)) == pytest.approx(12.0)
    write(tmp_path, f"{bat}/power_now", 8_500_000)     # 8.5 W, preferred when present
    assert sensors_linux.battery_watts(str(tmp_path)) == pytest.approx(8.5)
    write(tmp_path, f"{bat}/status", "Charging")
    assert sensors_linux.battery_watts(str(tmp_path)) is None


def test_linux_rapl_counters_become_component_watts(tmp_path, monkeypatch):
    zones = {"intel-rapl:0": ("package-0", 1_000_000), "intel-rapl:0:0": ("core", 500_000),
             "intel-rapl:0:1": ("uncore", 100_000), "intel-rapl:0:2": ("dram", 50_000)}
    for zone, (name, energy) in zones.items():
        write(tmp_path, f"sys/class/powercap/{zone}/name", name)
        write(tmp_path, f"sys/class/powercap/{zone}/energy_uj", energy)
        write(tmp_path, f"sys/class/powercap/{zone}/max_energy_range_uj", 2_000_000)
    clock = iter([100.0, 102.0])
    monkeypatch.setattr(sensors_linux.time, "monotonic", lambda: next(clock))
    sensors = sensors_linux.LinuxSensors(str(tmp_path))
    assert sensors.sources()["cpu"] == "RAPL (powercap)" and sensors.sources()["memory"] == "RAPL DRAM"
    # Two seconds later: core +10 J, uncore +2 J, dram +1 J; the package counter wrapped around.
    for zone, energy in {"intel-rapl:0": 100_000, "intel-rapl:0:0": 10_500_000,
                         "intel-rapl:0:1": 2_100_000, "intel-rapl:0:2": 1_050_000}.items():
        write(tmp_path, f"sys/class/powercap/{zone}/energy_uj", energy)
    parts = sensors.read_components()
    assert parts == {"cpu": pytest.approx(5.0), "gpu": pytest.approx(1.0), "memory": pytest.approx(0.5)}


def test_linux_amd_gpu(tmp_path):
    dev = "sys/class/drm/card0/device"
    write(tmp_path, f"{dev}/vendor", "0x1002")
    write(tmp_path, f"{dev}/gpu_busy_percent", 73)
    write(tmp_path, f"{dev}/hwmon/hwmon3/power1_average", 145_000_000)
    sensors = sensors_linux.LinuxSensors(str(tmp_path))
    assert sensors.gpu_percent() == 73 and sensors.read_components() == {"gpu": pytest.approx(145.0)}
    assert sensors.sources()["gpu"] == "amdgpu hwmon"


def test_linux_devices_from_sysfs(tmp_path):
    write(tmp_path, "sys/class/dmi/id/chassis_type", 10)
    write(tmp_path, "sys/class/dmi/id/sys_vendor", "LENOVO")
    write(tmp_path, "sys/class/dmi/id/product_name", "ThinkPad X1 Carbon Gen 12")
    write(tmp_path, "proc/cpuinfo", "processor\t: 0\nmodel name\t: Intel(R) Core(TM) Ultra 7 155U\n")
    write(tmp_path, "sys/block/nvme0n1/queue/rotational", 0)
    write(tmp_path, "sys/block/nvme0n1/size", 1_000_215_216)
    write(tmp_path, "sys/block/sda/queue/rotational", 1)
    write(tmp_path, "sys/block/sda/size", 3_907_029_168)
    write(tmp_path, "sys/block/loop0/size", 100)
    write(tmp_path, "sys/class/drm/card1-eDP-1/status", "connected")
    write(tmp_path, "sys/class/drm/card1-HDMI-A-1/status", "disconnected")
    write(tmp_path, "sys/class/drm/card1/device/vendor", "0x8086")
    found = linux_devices(str(tmp_path))
    assert found["device"] == {"manufacturer": "LENOVO", "model": "ThinkPad X1 Carbon Gen 12", "type": "laptop"}
    assert found["cpu"] == "Intel(R) Core(TM) Ultra 7 155U"
    assert [(d["name"], d["type"], d["size_gb"]) for d in found["disks"]] == [
        ("nvme0n1", "nvme", 512), ("sda", "hdd", 2000)]
    assert found["displays"] == [{"name": "Built-in display", "built_in": True}]
    assert found["gpus"] == [{"name": "Intel GPU", "type": "integrated", "cores": None, "vram": None}]


def test_lspci_gpu_names():
    out = ('00:02.0 "VGA compatible controller" "Intel Corporation" "Alder Lake-P GT2 [Iris Xe Graphics]" -r0c "" ""\n'
           '01:00.0 "3D controller" "NVIDIA Corporation" "AD107M [GeForce RTX 4060 Max-Q]" -ra1 "" ""\n'
           '00:1f.3 "Audio device" "Intel Corporation" "Alder Lake PCH-P High Definition Audio" "" ""')
    assert [(g["name"], g["type"]) for g in parse_lspci(out)] == [
        ("Intel Alder Lake-P GT2 [Iris Xe Graphics]", "integrated"),
        ("NVIDIA AD107M [GeForce RTX 4060 Max-Q]", "discrete")]


# --- Windows and NVIDIA ------------------------------------------------------

def test_windows_gpu_counts_compute_engines_and_reports_per_process():
    luid = "luid_0x00000000_0x0000D1B2_phys_0"
    items = [(f"pid_100_{luid}_eng_0_engtype_3D", 12.0),        # a game
             (f"pid_200_{luid}_eng_3_engtype_Cuda", 60.0),      # Ollama on CUDA
             (f"pid_201_{luid}_eng_3_engtype_Cuda", 25.0),      # another CUDA process
             (f"pid_100_{luid}_eng_1_engtype_Copy", 0.0)]
    pct, by_pid = gpu_engine_usage(items)
    assert pct == 85.0  # the busiest engine (Cuda), not 3D alone and not 3D + Cuda
    assert by_pid == {100: 12.0, 200: 60.0, 201: 25.0}


def test_nvidia_smi_parsing():
    assert parse_nvidia_gpus("285.40, 97\n31.20, 0\n") == (pytest.approx(316.6), 97.0)
    assert parse_nvidia_gpus("[N/A], 40\n") == (None, 40.0)
    assert parse_nvidia_compute_pids("4242\n 977 \n") == {4242, 977}


# --- Attribution -------------------------------------------------------------

def app(name, kind, cpu, pids):
    return {"app": name, "kind": kind, "cpu_percent": cpu, "pids": pids}


def test_measured_gpu_power_goes_to_the_processes_using_the_gpu():
    model = PowerModel(idle_watts=40, watts_per_cpu_pct=0.65, watts_per_gpu_pct=1.5)
    apps = [app("Ollama", "local", 100.0, [200]), app("Claude Code", "client", 10.0, [300])]
    # Windows: per-process GPU %. Ollama has 60 of 75 GPU-% points; the rest is a game.
    attribute(model, 75, apps, ncpu=10, cpu_pct=20, measured={"cpu": 30.0, "gpu": 250.0},
              gpu_by_pid={200: 60.0, 100: 15.0})
    assert apps[0]["watts"] == pytest.approx(30.0 * 10 / 20 + 250.0 * 60 / 75)
    assert apps[1]["watts"] == pytest.approx(30.0 * 1 / 20)


def test_nvidia_compute_list_keeps_a_game_off_the_local_model():
    model = PowerModel()
    apps = [app("Ollama", "local", 5.0, [200])]
    attribute(model, 90, apps, ncpu=8, measured={"gpu": 280.0}, gpu_pids={999})  # only a game uses CUDA
    assert apps[0]["watts"] == pytest.approx(model.watts_per_cpu_pct * 5 / 8, abs=1e-3)  # rounded to mW
    attribute(model, 90, apps, ncpu=8, measured={"gpu": 280.0}, gpu_pids={200, 999})
    assert apps[0]["watts"] == pytest.approx(model.watts_per_cpu_pct * 5 / 8 + 280.0, abs=1e-3)


def test_idle_local_runner_gets_no_gpu_power():
    apps = [app("Ollama", "local", 0.2, [1])]
    attribute(PowerModel(), 50, apps, ncpu=8, measured={"gpu": 40.0})
    assert apps[0]["watts"] == pytest.approx(PowerModel().watts_per_cpu_pct * 0.2 / 8, abs=1e-3)


def test_default_power_model_depends_on_the_device():
    assert default_power_model({"apple_silicon": True}) == PowerModel()
    desktop = default_power_model({"device": {"type": "desktop"}, "gpus": [{"type": "discrete"}]})
    laptop = default_power_model({"device": {"type": "laptop"}, "gpus": [{"type": "integrated"}]})
    assert desktop.idle_watts > laptop.idle_watts > PowerModel().idle_watts
    assert desktop.watts_per_gpu_pct > laptop.watts_per_gpu_pct


# --- Ollama and LM Studio ----------------------------------------------------

def manifest(models_dir, rel, blob):
    write(models_dir, f"manifests/{rel}", json.dumps({"layers": [
        {"mediaType": "application/vnd.ollama.image.model", "digest": f"sha256:{blob}"},
        {"mediaType": "application/vnd.ollama.image.template", "digest": "sha256:t"}]}))


def test_ollama_runners_are_named_from_their_manifests(tmp_path, monkeypatch):
    manifest(tmp_path, "registry.ollama.ai/library/llama3/8b", "aaa")
    manifest(tmp_path, "registry.ollama.ai/library/llama3/latest", "aaa")  # same weights, two names
    manifest(tmp_path, "registry.ollama.ai/library/qwen2.5/32b", "bbb")
    manifest(tmp_path, "hf.co/bartowski/Phi-4-GGUF/Q4_K_M", "ccc")
    monkeypatch.setattr(local_models, "ollama_loaded_models", lambda: [
        {"name": "llama3:latest", "size": 1, "size_vram": 1, "expires_at": 1}])
    blobs = tmp_path / "blobs"
    rows = [{"app": "Ollama", "model": None, "kind": "local", "cpu_percent": 90.0, "rss_mb": 5000.0, "pids": [2],
             "model_path": str(blobs / "sha256-aaa")},
            {"app": "Ollama", "model": None, "kind": "local", "cpu_percent": 0.5, "rss_mb": 19000.0, "pids": [3],
             "model_path": str(blobs / "sha256-ccc")},
            {"app": "Ollama", "model": None, "kind": "local", "cpu_percent": 0.1, "rss_mb": 50.0, "pids": [1],
             "model_path": None}]
    out = local_models.label_local_models(rows)
    assert [r["model"] for r in out] == ["Ollama · llama3:latest", "Ollama · hf.co/bartowski/Phi-4-GGUF:Q4_K_M",
                                         None]


def test_ollama_without_runner_processes_gives_the_work_to_the_last_used_model(monkeypatch):
    monkeypatch.setattr(local_models, "ollama_loaded_models", lambda: [
        {"name": "llama3:8b", "size": 5, "size_vram": 5, "expires_at": 100.0},
        {"name": "qwen2.5:32b", "size": 15, "size_vram": 15, "expires_at": 200.0}])
    rows = [{"app": "Ollama", "model": None, "kind": "local", "cpu_percent": 80.0, "rss_mb": 2000.0, "pids": [1],
             "model_path": None}]
    out = {r["model"]: r for r in local_models.label_local_models(rows)}
    assert out["Ollama · qwen2.5:32b"]["cpu_percent"] == 80.0
    assert out["Ollama · llama3:8b"]["cpu_percent"] == 0.0  # loaded but idle: recorded as such
    assert out["Ollama · llama3:8b"]["rss_mb"] == pytest.approx(500.0)


def test_lms_ps_and_ollama_times():
    out = json.dumps([{"identifier": "qwen2.5-7b-instruct", "sizeBytes": 4_700_000_000}, {"other": 1}])
    assert local_models.parse_lms_ps(out) == [{"name": "qwen2.5-7b-instruct", "size": 4_700_000_000}]
    assert local_models.parse_lms_ps("not json") == []
    assert local_models._parse_time("2026-10-09T14:38:31.837531234-07:00") == pytest.approx(
        local_models._parse_time("2026-10-09T21:38:31.837531Z"))


def test_model_path_from_runner_arguments():
    argv = ["/usr/local/bin/ollama", "runner", "--ollama-engine", "--model", "C:\\Users\\Jo Ann\\blobs\\sha256-a"]
    assert flag_value(argv, "--model") == "C:\\Users\\Jo Ann\\blobs\\sha256-a"  # spaces kept
    assert flag_value(["llama-server", "--model=/m/x.gguf"], "--model") == "/m/x.gguf"


# --- Storage -------------------------------------------------------------------

def test_active_and_idle_time_and_measured_days(tmp_path):
    conn = storage.connect(str(tmp_path / "t.db"))
    now = time.time()
    busy = {"app": "Ollama", "model": "Ollama · llama3:8b", "kind": "local", "cpu_percent": 90, "rss_mb": 5000,
            "watts": 30.0}
    idle = {**busy, "cpu_percent": 0.2, "watts": 0.1}
    for i in range(3):
        storage.save_sample(conn, now - 10 * i, 3600, 20, 50, 40, None, [busy if i == 0 else idle], device_id=1)
    storage.save_sample(conn, now - 30, 3600, 5, 0, 10, None, [], device_id=2)  # another computer
    (row,) = storage.daily_usage(conn, device_id=1)
    assert row["active_hours"] == pytest.approx(1.0) and row["kwh"] == pytest.approx(0.0302)
    (i,) = storage.idle_loaded(conn, device_id=1)
    assert i["idle_hours"] == pytest.approx(2.0) and i["kwh"] == pytest.approx(0.0002)
    assert [d["hours"] for d in storage.measured_days(conn, device_id=1)] == [pytest.approx(3.0)]
    assert sum(d["hours"] for d in storage.measured_days(conn)) == pytest.approx(4.0)


def test_power_model_is_kept_per_device(tmp_path):
    conn = storage.connect(str(tmp_path / "t.db"))
    storage.set_power_model(conn, PowerModel(idle_watts=4.0), device_id=1)
    storage.set_power_model(conn, PowerModel(idle_watts=45.0), device_id=2)
    assert storage.get_power_model(conn, 1).idle_watts == 4.0
    assert storage.get_power_model(conn, 2).idle_watts == 45.0
    assert storage.get_power_model(conn, 3) is None
