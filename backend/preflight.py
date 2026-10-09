"""Checks this computer is ready for the live demo: sensors, GPU, Ollama, database, backend.

    python preflight.py              # all checks, about 10 seconds
    python preflight.py --no-load    # skip the GPU load test (Ollama not installed yet)

Runs the same code the dashboard uses, so a PASS here means the dashboard will read it too.
Each line is PASS, WARN (works, but less is measured) or FAIL (fix before the demo), with
what to do. Run it once after setting up a new machine and again 30 minutes before the demo.
"""

import argparse
import json
import os
import platform
import sys
import time
import urllib.request

RESULTS = []
COLORS = {"PASS": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m", "INFO": "\033[36m"}


def report(status, check, detail, fix=None):
    RESULTS.append(status)
    color, reset = (COLORS[status], "\033[0m") if sys.stdout.isatty() else ("", "")
    print(f"  {color}{status:4}{reset}  {check:<22} {detail}")
    if fix and status != "PASS":
        print(f"        {'':<22} → {fix}")


def section(title):
    print(f"\n{title}")


def _get(url, body=None, timeout=3):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def check_python():
    section("Python")
    ok = sys.version_info >= (3, 10)
    report("PASS" if ok else "FAIL", "version", platform.python_version(), "install Python 3.10 or newer")
    missing = []
    for module in ("flask", "flask_cors", "dotenv", "psutil", "numpy"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    report("FAIL" if missing else "PASS", "packages", f"missing: {', '.join(missing)}" if missing else "all installed",
           "pip install -r requirements.txt (inside the .venv)")


def check_hardware():
    from app.services.system_info import detect_system

    section("Hardware")
    system = detect_system()
    device = system.get("device") or {}
    report("INFO", "OS", f"{system['os']} {system.get('os_version', '')} ({system.get('arch', '')}), "
                         f"{device.get('type', 'unknown type')}")
    report("INFO", "CPU / RAM", f"{system.get('cpu') or '?'}, {system.get('memory_gb', '?')} GB RAM")
    gpus = system.get("gpus") or []
    for g in gpus:
        vram = f", {g['vram']}" if g.get("vram") else ""
        report("INFO", "GPU", f"{g.get('name', '?')} ({g.get('type', '?')}{vram})")
    discrete = [g for g in gpus if g.get("type") == "discrete"]
    if discrete and not system.get("nvidia_gpu") and any("nvidia" in (g.get("name") or "").lower() for g in discrete):
        report("FAIL", "nvidia-smi", "NVIDIA GPU found but nvidia-smi isn't on PATH",
               "install/update the NVIDIA driver; nvidia-smi.exe comes with it (C:\\Windows\\System32)")
    elif not gpus:
        report("WARN", "GPU", "no GPU detected", "check that PowerShell runs (Windows) or the GPU driver is installed")
    return system


def check_sensors(system):
    import psutil

    from app.services.attribution import default_power_model
    from app.services.measurement import Sensors

    section("Power sensors")
    sensors = Sensors(system=system)
    sources = sensors.sources()
    for part in ("system", "cpu", "gpu", "memory", "disk"):
        src = sources.get(part)
        report("PASS" if src else "WARN", part, f"measured by {src}" if src else "estimated (no sensor)",
               _sensor_fix(system, part))

    if system["os"] == "windows" and sensors.platform:
        channels = sensors.platform.channels
        report("PASS" if channels else "WARN", "EMI channels", ", ".join(channels) or "none readable",
               "Energy Meter Interface missing or access denied: run the terminal as Administrator once "
               "to see whether it appears; without it CPU watts are estimated")
        report("PASS" if sensors.platform.gpu else "WARN", "GPU counters",
               "per-process GPU % available" if sensors.platform.gpu else "not available",
               "GPU share per app falls back to nvidia-smi's process list")

    # Two readings 2 s apart, like the collector: counters need a first sample.
    psutil.cpu_percent(None)
    sensors.gpu_percent()
    time.sleep(2)
    cpu, gpu = psutil.cpu_percent(None), sensors.gpu_percent()
    tel = sensors.system_power()
    parts = sensors.components(cpu, gpu or 0.0, default_power_model(system), tel["watts"] if tel else None)
    watts = ", ".join(f"{k} {v['watts']:.1f} W{'' if v['source'] == 'estimated' else '*'}" for k, v in parts.items())
    report("INFO", "live reading", f"CPU {cpu:.0f}%, GPU {gpu if gpu is not None else '?'}% · {watts}  (* measured)")
    if tel:
        report("PASS", "whole machine", f"{tel['watts']:.1f} W")
    elif system["os"] == "windows":
        report("WARN", "whole machine", "not measured while plugged in (Windows reports it on battery only)",
               "fine for the demo: GPU and CPU are still measured. Use the wall meter for the whole-machine number")

    if sensors.nvidia:
        nv_watts = sensors.nvidia.watts()
        report("PASS" if nv_watts is not None else "FAIL", "nvidia-smi power",
               f"{nv_watts:.1f} W" if nv_watts is not None else "no power.draw reading",
               "run `nvidia-smi` by hand; some laptop drivers report [N/A] for power — update the driver")
        pids = sensors.gpu_compute_pids()
        report("PASS" if pids is not None else "WARN", "nvidia-smi processes",
               f"{len(pids)} compute process(es)" if pids is not None else "can't list GPU processes",
               "per-process GPU % from Windows counters is used instead")
    return sensors


def _sensor_fix(system, part):
    if system["os"] == "windows":
        return {"system": "only on battery; plug-in power meter for the whole machine",
                "cpu": "needs the Energy Meter Interface (Intel/AMD RAPL)",
                "gpu": "install the NVIDIA driver (nvidia-smi)"}.get(part)
    if system["os"] == "macos":
        return {"cpu": "optional: passwordless `sudo powermetrics`"}.get(part)
    return None


def check_ollama(load_test, sensors):
    from app.services.local_models import ollama_installed_models, ollama_loaded_models, ollama_url
    from app.services.models_catalog import model_bytes
    from app.services.recommendations import SMALLER_MAX_RATIO

    section("Ollama (local models)")
    url = ollama_url()
    try:
        _get(f"{url}/api/version")
    except OSError:
        report("FAIL", "server", f"not reachable at {url}",
               "install from ollama.com and start it (tray icon), or run `ollama serve`")
        return
    report("PASS", "server", url)
    installed = ollama_installed_models()
    report("PASS" if installed else "FAIL", "installed models", ", ".join(m["name"] for m in installed) or "none",
           "ollama pull llama3.1:8b && ollama pull llama3.2:3b")

    # The SWITCH demo needs a big model and a smaller one of the same family (recommendations._smaller).
    pairs = [(big["name"], small["name"]) for big in installed for small in installed
             if big is not small and big.get("family") and big.get("family") == small.get("family")
             and model_bytes(big) and model_bytes(small) and model_bytes(small) <= model_bytes(big) * SMALLER_MAX_RATIO]
    if pairs:
        big, small = max(pairs, key=lambda p: next(model_bytes(m) for m in installed if m["name"] == p[0]))
        report("PASS", "switch pair", f"{big} → {small}")
    else:
        report("FAIL", "switch pair", "no big + small model of the same family",
               "pull two sizes of one family, e.g. llama3.1:8b and llama3.2:3b")

    loaded = ollama_loaded_models()
    if loaded:
        report("INFO", "loaded now", ", ".join(f"{m['name']} ({m['size_vram'] / 2**30:.1f} GB on GPU)" for m in loaded))

    if not load_test or not installed:
        return
    model = pairs[0][1] if pairs else installed[0]["name"]
    idle = sensors.nvidia.watts() if sensors.nvidia else None
    print(f"        {'':<22} running {model} for a few seconds to check the GPU picks it up…")
    try:
        res = _get(f"{url}/api/generate", {"model": model, "prompt": "Count from 1 to 40.", "stream": False,
                                           "options": {"num_predict": 120}}, timeout=180)
    except OSError as e:
        report("FAIL", "generate", str(e), "check `ollama run <model>` works in a terminal")
        return
    busy = sensors.nvidia.watts() if sensors.nvidia else None
    seconds = (res.get("eval_duration") or 0) / 1e9
    speed = f"{res.get('eval_count', 0) / seconds:.0f} tok/s" if seconds else "done"
    loaded = {m["name"]: m for m in ollama_loaded_models()}
    on_gpu = loaded.get(model, {}).get("size_vram", 0)
    total = loaded.get(model, {}).get("size", 0) or 1
    report("PASS" if on_gpu else "WARN", "runs on GPU", f"{speed}, {on_gpu / total:.0%} of {model} in VRAM",
           "Ollama is using the CPU: update the NVIDIA driver, or the model is too big for VRAM")
    if idle is not None and busy is not None:
        report("INFO", "GPU watts", f"{idle:.1f} W before → {busy:.1f} W just after generating")


def check_database():
    from app.config import Config
    from app.services import storage

    section("Database")
    try:
        conn = storage.connect(Config.DATABASE)
        conn.close()
        report("PASS", "storage", storage.describe(Config.DATABASE))
    except Exception as e:  # noqa: BLE001 — any driver error means the same fix
        report("FAIL", "storage", f"{storage.describe(Config.DATABASE)}: {e}",
               "remove DATABASE_URL from backend/.env to use the built-in SQLite file")


def check_settings():
    from app.config import Config

    section("Settings (backend/.env)")
    report("INFO", "tariff", f"₱{Config.ELECTRICITY_RATE}/kWh, {Config.TARIFF}, budget ₱{Config.MONTHLY_BUDGET:,.0f}")
    report("PASS" if Config.ELECTRICITYMAPS_TOKEN else "WARN", "Electricity Maps",
           f"token set, zone {Config.ELECTRICITYMAPS_ZONE}" if Config.ELECTRICITYMAPS_TOKEN else "no token",
           "optional: cleanest-hours card stays empty. Free token at app.electricitymaps.com → ELECTRICITYMAPS_TOKEN")


def check_backend():
    section("Dashboard")
    try:
        _get("http://127.0.0.1:5001/api/health", timeout=2)
        report("PASS", "backend", "running on http://127.0.0.1:5001")
    except OSError:
        report("WARN", "backend", "not running", "start it: python run.py")
        return
    try:
        status = _get("http://127.0.0.1:5001/api/device/status", timeout=5)
        running = status.get("running") or status.get("external_collector")
        report("PASS" if running else "WARN", "device reader",
               f"reading, {status.get('stored_samples', 0)} samples stored" if running else "not reading",
               "dashboard → This Device → Start reading my device")
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-load", action="store_true", help="skip the short Ollama GPU test")
    args = parser.parse_args()
    if sys.platform == "win32":
        os.system("")  # turns on ANSI colors in the classic Windows console
    sys.stdout.reconfigure(errors="replace")  # "₱" and "→" on a cp1252 console

    check_python()
    if "FAIL" in RESULTS:
        return 1
    system = check_hardware()
    sensors = check_sensors(system)
    check_ollama(not args.no_load, sensors)
    check_database()
    check_settings()
    check_backend()

    fails, warns = RESULTS.count("FAIL"), RESULTS.count("WARN")
    print(f"\n{fails} to fix, {warns} warning(s)." + (" Ready for the demo." if not fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
