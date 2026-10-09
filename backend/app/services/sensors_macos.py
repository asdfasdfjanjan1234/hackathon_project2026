"""macOS sensors.

No sudo needed:
  ioreg -rn AppleSmartBattery      whole-laptop power, averaged by the battery controller
  ioreg -r -d 1 -c IOAccelerator   GPU utilization %
  IOReport "GPU Energy" channel    GPU energy (Apple Silicon), read through libIOReport
Only with passwordless sudo:
  powermetrics                     CPU and GPU power

On macOS 27 (M2) the IOReport CPU and DRAM channels don't update without root,
so CPU and memory watts are estimated unless powermetrics is available.
"""

import ctypes
import ctypes.util
import re
import shutil
import subprocess
import time


def _run(cmd, timeout=5):
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return out.stdout if out.returncode == 0 else None


def read_battery_telemetry():
    """Whole-laptop power from the battery controller (Apple Silicon laptops).

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


def powermetrics_available():
    if not shutil.which("powermetrics"):
        return False
    try:
        return subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def parse_powermetrics(text):
    """{"cpu": W, "gpu": W, "ane": W} from powermetrics output."""
    out = {}
    for key, label in (("cpu", "CPU"), ("gpu", "GPU"), ("ane", "ANE")):
        match = re.search(rf"^{label} Power: (\d+) mW", text or "", re.MULTILINE)
        if match:
            out[key] = int(match.group(1)) / 1000
    return out


def read_powermetrics():
    """Takes about half a second. Works only when sudo needs no password."""
    try:
        out = _run(["sudo", "-n", "powermetrics", "--samplers", "cpu_power,gpu_power", "-n", "1", "-i", "500"],
                   timeout=10)
    except (subprocess.SubprocessError, OSError):
        return {}
    return parse_powermetrics(out)


class IOReportEnergy:
    """Running energy totals from Apple's IOReport "Energy Model" channels, without sudo.

    joules() returns {channel name: joules so far}; subtract two readings to get energy
    over the interval. Raises OSError where IOReport isn't available.
    """

    UNITS = {"mJ": 1e-3, "uJ": 1e-6, "nJ": 1e-9}

    def __init__(self, channels=("GPU Energy",)):
        self.wanted = set(channels)
        V = ctypes.c_void_p
        cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
        ior = ctypes.CDLL("/usr/lib/libIOReport.dylib")
        for fn, res, args in [
            (cf.CFStringCreateWithCString, V, [V, ctypes.c_char_p, ctypes.c_uint32]),
            (cf.CFStringGetCString, ctypes.c_bool, [V, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]),
            (cf.CFDictionaryGetValue, V, [V, V]),
            (cf.CFDictionaryGetCount, ctypes.c_long, [V]),
            (cf.CFDictionaryCreateMutableCopy, V, [V, ctypes.c_long, V]),
            (cf.CFArrayGetCount, ctypes.c_long, [V]),
            (cf.CFArrayGetValueAtIndex, V, [V, ctypes.c_long]),
            (cf.CFRelease, None, [V]),
            (ior.IOReportCopyChannelsInGroup, V, [V, V, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64]),
            (ior.IOReportCreateSubscription, V, [V, V, ctypes.POINTER(V), ctypes.c_uint64, V]),
            (ior.IOReportCreateSamples, V, [V, V, V]),
            (ior.IOReportChannelGetChannelName, V, [V]),
            (ior.IOReportChannelGetUnitLabel, V, [V]),
            (ior.IOReportSimpleGetIntegerValue, ctypes.c_int64, [V, V]),
        ]:
            fn.restype, fn.argtypes = res, args
        self.cf, self.ior = cf, ior
        self._key = self._cfstr("IOReportChannels")

        group = ior.IOReportCopyChannelsInGroup(self._cfstr("Energy Model"), None, 0, 0, 0)
        if not group:
            raise OSError("IOReport Energy Model group not found")
        # Subscribing needs a mutable copy of the channel list.
        self._channels = cf.CFDictionaryCreateMutableCopy(None, cf.CFDictionaryGetCount(group), group)
        self._sub_channels = V()
        self._sub = ior.IOReportCreateSubscription(None, self._channels, ctypes.byref(self._sub_channels), 0, None)
        if not self._sub:
            raise OSError("IOReport subscription failed")

    def _cfstr(self, s):
        return self.cf.CFStringCreateWithCString(None, s.encode(), 0x08000100)  # UTF-8

    def _pystr(self, ref):
        if not ref:
            return ""
        buf = ctypes.create_string_buffer(256)
        return buf.value.decode() if self.cf.CFStringGetCString(ref, buf, 256, 0x08000100) else ""

    def joules(self):
        sample = self.ior.IOReportCreateSamples(self._sub, self._sub_channels, None)
        if not sample:
            return {}
        try:
            items = self.cf.CFDictionaryGetValue(sample, self._key)
            out = {}
            for i in range(self.cf.CFArrayGetCount(items) if items else 0):
                item = self.cf.CFArrayGetValueAtIndex(items, i)
                name = self._pystr(self.ior.IOReportChannelGetChannelName(item))
                if name not in self.wanted:
                    continue
                scale = self.UNITS.get(self._pystr(self.ior.IOReportChannelGetUnitLabel(item)).strip())
                if scale:
                    out[name] = self.ior.IOReportSimpleGetIntegerValue(item, None) * scale
            return out
        finally:
            self.cf.CFRelease(sample)


class MacSensors:
    def __init__(self, apple_silicon=True):
        self.gpu_energy = None
        if apple_silicon:
            try:
                self.gpu_energy = IOReportEnergy(("GPU Energy",))
            except (OSError, AttributeError):
                self.gpu_energy = None
        self.powermetrics = powermetrics_available()
        self._last = None  # (time, GPU joules)
        if self.gpu_energy:
            self.read_components()  # first reading, so the next one has something to subtract from

    def sources(self):
        return {
            "system": "battery (ioreg)",
            "cpu": "powermetrics" if self.powermetrics else None,
            "gpu": "powermetrics" if self.powermetrics else ("IOReport GPU Energy" if self.gpu_energy else None),
            "memory": None,
            "disk": None,
        }

    def system_power(self):
        return read_battery_telemetry()

    def gpu_percent(self):
        return read_gpu_utilization()

    def read_components(self):
        """Measured watts for the components this Mac exposes, e.g. {"gpu": 0.02}."""
        if self.powermetrics:
            pm = read_powermetrics()
            if pm:
                return {"cpu": pm.get("cpu", 0.0), "gpu": pm.get("gpu", 0.0) + pm.get("ane", 0.0)}
        if not self.gpu_energy:
            return {}
        now, joules = time.monotonic(), self.gpu_energy.joules().get("GPU Energy")
        last, self._last = self._last, (now, joules)
        if joules is None or last is None or last[1] is None or now <= last[0] or joules < last[1]:
            return {}
        return {"gpu": (joules - last[1]) / (now - last[0])}
