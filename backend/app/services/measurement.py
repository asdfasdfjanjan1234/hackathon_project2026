"""Reads power and resource use from this machine.

Apple Silicon laptops (no sudo needed):
  ioreg -rn AppleSmartBattery      system power, averaged by the battery controller
  ioreg -r -d 1 -c IOAccelerator   GPU utilization %
Optional, more detailed sources:
  sudo powermetrics --samplers cpu_power,gpu_power -n 1
  nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits
"""

import random
import re
import shutil
import subprocess


def _run(cmd, timeout=5):
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return out.stdout if out.returncode == 0 else None


def read_battery_telemetry():
    """System power from the battery controller (Apple Silicon laptops).

    watts: latest reading. accum/count: running totals; the difference between
    two readings divided by the difference in count is the average mW in between.
    """
    if not shutil.which("ioreg"):
        return None
    try:
        out = _run(["ioreg", "-rn", "AppleSmartBattery"])
    except (subprocess.SubprocessError, OSError):
        return None
    block = re.search(r'"PowerTelemetryData" = \{([^}]*)\}', out or "")
    if not block:
        return None
    fields = {k: int(v) for k, v in re.findall(r'"(\w+)"=(\d+)', block.group(1))}
    load_mw = fields.get("SystemLoad") or fields.get("SystemPowerIn")
    if not load_mw or "AccumulatedSystemLoad" not in fields:
        return None
    return {
        "watts": load_mw / 1000,
        "accum": fields["AccumulatedSystemLoad"],
        "count": fields.get("SystemLoadAccumulatorCount", 0),
    }


def read_gpu_utilization():
    if not shutil.which("ioreg"):
        return None
    try:
        out = _run(["ioreg", "-r", "-d", "1", "-c", "IOAccelerator"])
    except (subprocess.SubprocessError, OSError):
        return None
    match = re.search(r'"Device Utilization %"=(\d+)', out or "")
    return float(match.group(1)) if match else None


def _read_nvidia_watts():
    if not shutil.which("nvidia-smi"):
        return None
    out = _run(["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"])
    return sum(float(line) for line in out.split() if line.strip()) if out else None


def _read_powermetrics_watts():
    """Works only when the process can run powermetrics without a password prompt."""
    if not shutil.which("powermetrics"):
        return None
    out = _run(["sudo", "-n", "powermetrics", "--samplers", "cpu_power,gpu_power", "-n", "1", "-i", "500"], timeout=10)
    match = re.search(r"Combined Power \(CPU \+ GPU \+ ANE\): (\d+) mW", out or "")
    return int(match.group(1)) / 1000 if match else None


def _read_battery_watts():
    tel = read_battery_telemetry()
    return tel["watts"] if tel else None


def read_live_power():
    """Fallback for /api/live when the collector isn't running: total watts only."""
    readers = (("nvidia-smi", _read_nvidia_watts), ("powermetrics", _read_powermetrics_watts),
               ("battery", _read_battery_watts))
    for source, reader in readers:
        try:
            watts = reader()
        except (subprocess.SubprocessError, OSError, ValueError):
            watts = None
        if watts is not None:
            return {"watts": round(watts, 1), "source": source, "simulated": False, "apps": []}
    return {"watts": round(random.uniform(15, 90), 1), "source": "simulated", "simulated": True, "apps": []}
