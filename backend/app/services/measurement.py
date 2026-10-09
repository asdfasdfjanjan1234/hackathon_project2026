"""Reads live power draw from this machine.

Apple Silicon: `sudo powermetrics --samplers cpu_power,gpu_power -n 1`
NVIDIA:        `nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits`

powermetrics needs sudo, so the real collector should run as a separate
privileged process that writes readings to storage. Until then, this
returns simulated readings labeled as such.
"""

import random
import re
import shutil
import subprocess


def _read_nvidia_watts():
    if not shutil.which("nvidia-smi"):
        return None
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=5,
    )
    if out.returncode != 0:
        return None
    return sum(float(line) for line in out.stdout.split() if line.strip())


def _read_powermetrics_watts():
    """Works only when the process can run powermetrics without a password prompt."""
    if not shutil.which("powermetrics"):
        return None
    out = subprocess.run(
        ["sudo", "-n", "powermetrics", "--samplers", "cpu_power,gpu_power", "-n", "1", "-i", "500"],
        capture_output=True, text=True, timeout=10,
    )
    if out.returncode != 0:
        return None
    match = re.search(r"Combined Power \(CPU \+ GPU \+ ANE\): (\d+) mW", out.stdout)
    return int(match.group(1)) / 1000 if match else None


def read_live_power():
    for source, reader in (("nvidia-smi", _read_nvidia_watts), ("powermetrics", _read_powermetrics_watts)):
        try:
            watts = reader()
        except (subprocess.SubprocessError, OSError, ValueError):
            watts = None
        if watts is not None:
            return {"watts": round(watts, 1), "source": source, "simulated": False}
    return {"watts": round(random.uniform(15, 90), 1), "source": "simulated", "simulated": True}
