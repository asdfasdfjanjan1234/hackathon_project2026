"""Reads power per component (CPU, GPU, memory, disk) and for the whole machine.

The OS is detected once (system_info.detect_system), then the matching sensors are used:

  component  macOS (Apple Silicon)          Windows                         Linux                        fallback
  ---------  -----------------------------  ------------------------------  ---------------------------  ----------------------
  system     battery controller (ioreg)     battery rate (CallNtPowerInfo)  battery (sysfs)              none (desktop / on AC)
  cpu        powermetrics, only with sudo   EMI: RAPL cores / package       RAPL powercap (often root)   fitted CPU% formula
  gpu        IOReport GPU Energy, no sudo   EMI: RAPL PP1 (iGPU)            RAPL uncore, amdgpu hwmon    fitted GPU% formula
             (+ nvidia-smi on any OS for NVIDIA GPUs: power, utilization and which processes use the GPU)
  memory     not exposed without root       EMI: RAPL DRAM (mostly servers) RAPL DRAM                    RAM size × load estimate
  disk       not exposed                    not exposed                     not exposed                  disk type × busy time

Every component value carries its source, so measured and estimated numbers stay separate.
"""

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


def _nvidia_smi(*args):
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(["nvidia-smi", *args], capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout if out.returncode == 0 else None


def parse_nvidia_gpus(text):
    """(total watts, highest utilization %) from `--query-gpu=power.draw,utilization.gpu` CSV lines."""
    watts, util = [], []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        try:
            watts.append(float(parts[0]))
        except (ValueError, IndexError):
            pass
        try:
            util.append(float(parts[1]))
        except (ValueError, IndexError):
            pass
    return (sum(watts) if watts else None), (max(util) if util else None)


def parse_nvidia_compute_pids(text):
    """PIDs of processes running compute work (CUDA) on an NVIDIA GPU, from `--query-compute-apps=pid`."""
    return {int(line.strip()) for line in (text or "").splitlines() if line.strip().isdigit()}


class NvidiaReader:
    """nvidia-smi readings, shared by the power, utilization and process queries of one collector step."""

    MAX_AGE_S = 1.0

    def __init__(self):
        self._at, self._gpus = 0.0, (None, None)

    def _read(self):
        now = time.monotonic()
        if now - self._at > self.MAX_AGE_S:
            self._at = now
            self._gpus = parse_nvidia_gpus(_nvidia_smi("--query-gpu=power.draw,utilization.gpu",
                                                       "--format=csv,noheader,nounits"))
        return self._gpus

    def watts(self):
        return self._read()[0]

    def percent(self):
        return self._read()[1]

    @staticmethod
    def compute_pids():
        text = _nvidia_smi("--query-compute-apps=pid", "--format=csv,noheader")
        return None if text is None else parse_nvidia_compute_pids(text)


def _platform_sensors(system):
    if system["os"] == "macos":
        from .sensors_macos import MacSensors
        return MacSensors(apple_silicon=system["apple_silicon"])
    if system["os"] == "windows":
        from .sensors_windows import WindowsSensors
        return WindowsSensors()
    if system["os"] == "linux":
        from .sensors_linux import LinuxSensors
        return LinuxSensors()
    return None  # other OSes: nvidia-smi and estimates only


class Sensors:
    """Detects the OS, picks its sensors once, then reads them on every collector step."""

    def __init__(self, system=None, platform_sensors=None):
        self.system = system or detect_system()
        self.platform = platform_sensors if platform_sensors is not None else _platform_sensors(self.system)
        self.nvidia = NvidiaReader() if self.system.get("nvidia_gpu", False) else None
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
        """GPU utilization %: the OS's own counter, or the busiest NVIDIA GPU where the OS has none."""
        pct = self.platform.gpu_percent() if self.platform else None
        if self.nvidia:
            nv = self.nvidia.percent()
            if nv is not None:
                pct = max(pct or 0.0, nv)
        return pct

    def gpu_by_pid(self):
        """{pid: GPU %} where the OS reports GPU use per process (Windows), else None."""
        reader = getattr(self.platform, "gpu_by_pid", None)
        return reader() if reader else None

    def gpu_compute_pids(self):
        """PIDs running compute work on an NVIDIA GPU, or None when that can't be read."""
        return self.nvidia.compute_pids() if self.nvidia else None

    def components(self, cpu_pct, gpu_pct, power_model, system_watts=None):
        """Watts per component, each {"watts": W, "source": sensor name or "estimated"}.

        "other" is whatever the measured whole-machine power doesn't explain (display, Wi-Fi, ...).
        """
        measured = dict(self.platform.read_components()) if self.platform else {}
        sources = self.sources()
        if self.nvidia:
            nv = self.nvidia.watts()
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
            # The measured total caps the parts: when the estimates add up to more than the
            # measured parts leave room for, scale the estimates down to fit.
            guessed = [c for c in out.values() if c["source"] == "estimated"]
            room = max(system_watts - sum(c["watts"] for c in out.values() if c["source"] != "estimated"), 0.0)
            guessed_sum = sum(c["watts"] for c in guessed)
            if guessed_sum > room:
                for c in guessed:
                    c["watts"] = round(c["watts"] * room / guessed_sum, 3)
            rest = system_watts - sum(c["watts"] for c in out.values())
            out["other"] = {"watts": round(max(rest, 0.0), 3), "source": DERIVED}
        return out


@lru_cache(maxsize=1)
def default_sensors():
    return Sensors()


def read_live_power():
    """Fallback for /api/live when the collector isn't running: whole-machine watts only.

    Uses the whole-machine sensor, else NVIDIA GPU power plus a CPU estimate, else the
    default power formula. Anything not read from a sensor is labeled "estimated".
    """
    from .attribution import PowerModel

    sensors = default_sensors()
    tel = sensors.system_power()
    if tel:
        return {"watts": round(tel["watts"], 1), "source": sensors.sources()["system"],
                "estimated": False, "simulated": False, "apps": []}
    cpu = psutil.cpu_percent(None)
    model = PowerModel()
    gpu_watts = sensors.nvidia.watts() if sensors.nvidia else None
    if gpu_watts is not None:
        return {"watts": round(model.total(cpu, 0) + gpu_watts, 1), "source": "nvidia-smi + estimated CPU",
                "estimated": True, "simulated": False, "apps": []}
    return {"watts": round(model.total(cpu, sensors.gpu_percent() or 0.0), 1), "source": "estimated",
            "estimated": True, "simulated": False, "apps": []}
