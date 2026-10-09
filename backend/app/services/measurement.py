"""Reads power per component (CPU, GPU, memory, disk) and for the whole machine.

The OS is detected once (system_info.detect_system), then the matching sensors are used:

  component  macOS (Apple Silicon)               Windows                          fallback
  ---------  ----------------------------------  -------------------------------  -----------------------
  system     battery controller (ioreg)          battery rate (CallNtPowerInfo)   none (desktop / on AC)
  cpu        powermetrics, only with sudo        EMI: RAPL cores / package        fitted CPU% formula
  gpu        IOReport GPU Energy, no sudo        EMI: RAPL PP1 (iGPU)             fitted GPU% formula
             (+ nvidia-smi on any OS for NVIDIA GPUs)
  memory     not exposed without root            EMI: RAPL DRAM (mostly servers)  RAM size × load estimate
  disk       not exposed                         not exposed                      disk type × busy time

Every component value carries its source, so measured and estimated numbers stay separate.
"""

import random
import shutil
import subprocess
import time
from functools import lru_cache

import psutil

from .system_info import detect_system

COMPONENTS = ("cpu", "gpu", "memory", "disk")
DERIVED = "system − components"  # source label of "other"

# Rough defaults for components no OS reports. They give the right order of magnitude
# for laptop LPDDR/DDR memory and NVMe SSDs; replace them with measured values when possible.
MEMORY_IDLE_W_PER_GB = 0.03      # refresh and standby power
MEMORY_ACTIVE_W_PER_GB = 0.15    # extra power at full load
DISK_WATTS = {                   # (idle, busy) per disk, by the type system_info detected
    "nvme": (0.05, 3.0),
    "ssd": (0.05, 2.0),          # SATA SSD
    "hdd": (4.0, 6.0),           # 3.5-inch desktop drive; 2.5-inch laptop drives use about a third
}


def estimate_memory_watts(memory_gb, load_pct, active_only=False):
    """Memory traffic follows CPU/GPU load, so use the busier of the two as the activity level."""
    load = min(max(load_pct, 0.0), 100.0) / 100
    active = memory_gb * MEMORY_ACTIVE_W_PER_GB * load
    return active if active_only else memory_gb * MEMORY_IDLE_W_PER_GB + active


def estimate_disk_watts(busy_fraction, disks=None):
    """Every disk draws its idle power; busy time adds the largest disk's extra power."""
    busy = min(max(busy_fraction, 0.0), 1.0)
    watts = [DISK_WATTS.get(d.get("type"), DISK_WATTS["nvme"]) for d in disks or [{"type": "nvme"}]]
    return sum(idle for idle, _ in watts) + busy * max(active - idle for idle, active in watts)


class DiskActivity:
    """Fraction of time the disks were busy since the last call, from psutil read/write times."""

    def __init__(self):
        self._last = self._read()

    @staticmethod
    def _read():
        try:
            io = psutil.disk_io_counters()
        except (RuntimeError, OSError):
            return None
        if io is None or not hasattr(io, "read_time"):
            return None
        return time.monotonic(), io.read_time + io.write_time  # milliseconds

    def busy_fraction(self):
        cur, last = self._read(), self._last
        self._last = cur
        if not cur or not last or cur[0] <= last[0]:
            return 0.0
        return min(max((cur[1] - last[1]) / 1000 / (cur[0] - last[0]), 0.0), 1.0)


def read_nvidia_watts():
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return None
    try:
        values = [float(v) for v in out.stdout.split() if v.strip()] if out.returncode == 0 else []
    except ValueError:
        return None
    return sum(values) if values else None


def _platform_sensors(system):
    if system["os"] == "macos":
        from .sensors_macos import MacSensors
        return MacSensors(apple_silicon=system["apple_silicon"])
    if system["os"] == "windows":
        from .sensors_windows import WindowsSensors
        return WindowsSensors()
    return None  # Linux and others: nvidia-smi and estimates only


class Sensors:
    """Detects the OS, picks its sensors once, then reads them on every collector step."""

    def __init__(self, system=None, platform_sensors=None):
        self.system = system or detect_system()
        self.platform = platform_sensors if platform_sensors is not None else _platform_sensors(self.system)
        self.nvidia = self.system.get("nvidia_gpu", False)
        self.disk = DiskActivity()

    def sources(self):
        """Which sensor each component uses on this machine (None: estimated)."""
        found = self.platform.sources() if self.platform else {}
        if self.nvidia:
            found["gpu"] = " + ".join(s for s in (found.get("gpu"), "nvidia-smi") if s)
        return {k: found.get(k) for k in ("system",) + COMPONENTS}

    def system_power(self):
        """Whole-machine power: {"watts": W}, plus running totals on Macs. None when not measurable."""
        return self.platform.system_power() if self.platform else None

    def gpu_percent(self):
        return self.platform.gpu_percent() if self.platform else None

    def components(self, cpu_pct, gpu_pct, power_model, system_watts=None):
        """Watts per component, each {"watts": W, "source": sensor name or "estimated"}.

        "other" is whatever the measured whole-machine power doesn't explain (display, Wi-Fi, ...).
        """
        measured = dict(self.platform.read_components()) if self.platform else {}
        sources = self.sources()
        if self.nvidia:
            nv = read_nvidia_watts()
            if nv is not None:
                measured["gpu"] = measured.get("gpu", 0.0) + nv

        memory_gb, load = self.system.get("memory_gb", 8), max(cpu_pct, gpu_pct)
        estimates = {
            "cpu": power_model.watts_per_cpu_pct * cpu_pct,
            "gpu": power_model.watts_per_gpu_pct * gpu_pct,
            "memory": estimate_memory_watts(memory_gb, load),
            "disk": estimate_disk_watts(self.disk.busy_fraction(), self.system.get("disks")),
        }
        if "memory" not in measured:
            # The fitted CPU coefficient also covers the memory traffic CPU work causes,
            # so move that part to memory instead of counting it twice.
            estimates["cpu"] = max(estimates["cpu"] - estimate_memory_watts(memory_gb, load, active_only=True), 0.0)
        out = {}
        for k in COMPONENTS:
            if k in measured:
                out[k] = {"watts": round(measured[k], 3), "source": sources.get(k) or "measured"}
            else:
                out[k] = {"watts": round(estimates[k], 3), "source": "estimated"}
        if system_watts is not None:
            rest = system_watts - sum(c["watts"] for c in out.values())
            out["other"] = {"watts": round(max(rest, 0.0), 3), "source": DERIVED}
        return out


@lru_cache(maxsize=1)
def default_sensors():
    return Sensors()


def read_live_power():
    """Fallback for /api/live when the collector isn't running: whole-machine watts only."""
    sensors = default_sensors()
    tel = sensors.system_power()
    if tel:
        return {"watts": round(tel["watts"], 1), "source": sensors.sources()["system"], "simulated": False, "apps": []}
    watts = read_nvidia_watts()
    if watts is not None:
        return {"watts": round(watts, 1), "source": "nvidia-smi", "simulated": False, "apps": []}
    return {"watts": round(random.uniform(15, 90), 1), "source": "simulated", "simulated": True, "apps": []}
