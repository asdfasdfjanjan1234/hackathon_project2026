"""Linux sensors, read from sysfs (no extra installs).

  /sys/class/power_supply/BAT*        whole-laptop power while on battery (power_now, or current × voltage)
  /sys/class/powercap/intel-rapl:*    CPU package, cores, integrated GPU (uncore) and DRAM energy, Intel and AMD
  /sys/class/drm/card*/device         AMD GPU utilization (gpu_busy_percent) and power (hwmon power1_average)

Since 2020 most distributions make the RAPL counters readable by root only; without
access each reader returns None or {} and the caller falls back to estimates, as on
the other OSes. Every function takes a `root` so tests can point it at a fake sysfs.
"""

import glob
import os
import time


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _num(path):
    value = _read(path)
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _sys(root, *parts):
    return os.path.join(root, "sys", *parts)


# --- Battery ----------------------------------------------------------------

def batteries(root="/"):
    return [p for p in sorted(glob.glob(_sys(root, "class", "power_supply", "*")))
            if _read(os.path.join(p, "type")) == "Battery"]


def battery_watts(root="/"):
    """Total discharge power in watts, or None when on AC (the reading is then charge power or 0)."""
    total, found = 0.0, False
    for bat in batteries(root):
        if _read(os.path.join(bat, "status")) != "Discharging":
            continue
        power = _num(os.path.join(bat, "power_now"))  # µW
        if power is None:
            current, voltage = _num(os.path.join(bat, "current_now")), _num(os.path.join(bat, "voltage_now"))
            if current is None or voltage is None:
                continue
            power = current * voltage / 1e6  # µA × µV = pW → µW
        total += abs(power) / 1e6
        found = True
    return total if found else None


def battery_health(root="/"):
    for bat in batteries(root):
        full = _num(os.path.join(bat, "energy_full")) or _num(os.path.join(bat, "charge_full"))
        design = _num(os.path.join(bat, "energy_full_design")) or _num(os.path.join(bat, "charge_full_design"))
        cycles = _num(os.path.join(bat, "cycle_count"))
        if full and design:
            return {"max_capacity": f"{round(100 * full / design)}%", "cycles": int(cycles) if cycles else None}
    return None


# --- RAPL -------------------------------------------------------------------

def rapl_zones(root="/"):
    """{zone path: name} for every readable RAPL zone, e.g. "package-0", "core", "uncore", "dram", "psys"."""
    zones = {}
    for path in sorted(glob.glob(_sys(root, "class", "powercap", "intel-rapl:*"))):
        name = _read(os.path.join(path, "name"))
        if name and _num(os.path.join(path, "energy_uj")) is not None:
            zones[path] = name
    return zones


def rapl_components(watts_by_name):
    """Map RAPL zone watts (summed over sockets) to cpu / gpu / memory, as emi_components does on Windows."""
    out = {}
    pkg, core, uncore = (watts_by_name.get(k) for k in ("package", "core", "uncore"))
    if core is not None:
        out["cpu"] = core
    elif pkg is not None:
        out["cpu"] = max(pkg - (uncore or 0.0), 0.0)
    if uncore is not None:
        out["gpu"] = uncore  # integrated GPU on Intel
    if "dram" in watts_by_name:
        out["memory"] = watts_by_name["dram"]
    return out


class RaplMeter:
    """Watts per RAPL zone since the previous call, from the cumulative energy_uj counters."""

    def __init__(self, root="/"):
        self.zones = rapl_zones(root)
        self._last = self._sample()

    def _sample(self):
        out = {}
        for path in self.zones:
            energy = _num(os.path.join(path, "energy_uj"))
            if energy is not None:
                out[path] = (energy, _num(os.path.join(path, "max_energy_range_uj")))
        return time.monotonic(), out

    def watts(self):
        """{"package": W, "core": W, ...}, summed over sockets; {} until a second reading exists."""
        (t0, last), (t1, cur) = self._last, self._sample()
        self._last = (t1, cur)
        if t1 <= t0:
            return {}
        out = {}
        for path, (energy, wrap) in cur.items():
            if path not in last:
                continue
            delta = energy - last[path][0]
            if delta < 0:  # the counter wrapped around
                if not wrap:
                    continue
                delta += wrap
            name = self.zones[path].split("-")[0]  # "package-0" → "package"
            out[name] = out.get(name, 0.0) + delta / 1e6 / (t1 - t0)
        return out


# --- AMD GPU ----------------------------------------------------------------

def amd_gpus(root="/"):
    return [p for p in sorted(glob.glob(_sys(root, "class", "drm", "card[0-9]*", "device")))
            if _read(os.path.join(p, "vendor")) == "0x1002"]


def amd_gpu_percent(root="/"):
    values = [v for v in (_num(os.path.join(g, "gpu_busy_percent")) for g in amd_gpus(root)) if v is not None]
    return max(values) if values else None


def amd_gpu_watts(root="/"):
    total, found = 0.0, False
    for gpu in amd_gpus(root):
        for hwmon in glob.glob(os.path.join(gpu, "hwmon", "hwmon*")):
            power = _num(os.path.join(hwmon, "power1_average")) or _num(os.path.join(hwmon, "power1_input"))
            if power is not None:
                total += power / 1e6
                found = True
                break
    return total if found else None


class LinuxSensors:
    def __init__(self, root="/"):
        self.root = root
        self.has_battery = bool(batteries(root))
        self.rapl = RaplMeter(root)
        self.amd = bool(amd_gpus(root))
        self._rapl_parts = rapl_components({self.zone_name(n): 0.0 for n in self.rapl.zones.values()})

    @staticmethod
    def zone_name(name):
        return name.split("-")[0]

    def sources(self):
        parts = self._rapl_parts
        gpu = [s for s, ok in (("RAPL uncore", "gpu" in parts), ("amdgpu hwmon", self.amd)) if ok]
        return {
            "system": "battery (sysfs)" if self.has_battery else None,
            "cpu": "RAPL (powercap)" if "cpu" in parts else None,
            "gpu": " + ".join(gpu) or None,
            "memory": "RAPL DRAM" if "memory" in parts else None,
            "disk": None,
        }

    def system_power(self):
        watts = battery_watts(self.root)
        return {"watts": watts} if watts is not None else None

    def gpu_percent(self):
        return amd_gpu_percent(self.root) if self.amd else None

    def read_components(self):
        out = rapl_components(self.rapl.watts()) if self.rapl.zones else {}
        if self.amd:
            amd = amd_gpu_watts(self.root)
            if amd is not None:
                out["gpu"] = out.get("gpu", 0.0) + amd
        return out
