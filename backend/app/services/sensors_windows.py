"""Windows sensors, called through ctypes (no extra installs).

  Energy Meter Interface (EMI)     CPU, integrated GPU and DRAM energy from Intel/AMD RAPL
                                   (Windows 10 1809+; the inbox driver exposes it on most recent PCs)
  CallNtPowerInformation           whole-laptop power while on battery
  PDH "GPU Engine" counters        GPU utilization %

Each reader returns None or {} when the sensor is missing or access is denied, so
the caller falls back to estimates. The parsing functions are plain Python and are
unit-tested on any OS; the ctypes parts need a Windows machine to try.
"""

import ctypes
import struct
import time

# --- Energy Meter Interface -------------------------------------------------
# Device interface GUID_DEVICE_ENERGY_METER {45BD8344-7ED6-49cf-A440-C276C933B053}
EMI_GUID = (0x45BD8344, 0x7ED6, 0x49CF, (0xA4, 0x40, 0xC2, 0x76, 0xC9, 0x33, 0xB0, 0x53))


def _ctl_code(function):
    # CTL_CODE(FILE_DEVICE_UNKNOWN, function, METHOD_BUFFERED, FILE_READ_ACCESS)
    return (0x22 << 16) | (0x1 << 14) | (function << 2)


IOCTL_EMI_GET_VERSION, IOCTL_EMI_GET_METADATA_SIZE, IOCTL_EMI_GET_METADATA, IOCTL_EMI_GET_MEASUREMENT = (
    _ctl_code(i) for i in range(4))
JOULES_PER_PICOWATT_HOUR = 3.6e-9


def _wstr(raw):
    return raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]


def parse_emi_metadata(version, buf):
    """Channel names from an EMI_METADATA_V1 or EMI_METADATA_V2 buffer."""
    if version == 1:
        # MeasurementUnit (4), HardwareOEM (32), HardwareModel (32), HardwareRevision (2),
        # MeteredHardwareNameSize (2), MeteredHardwareName
        (size,) = struct.unpack_from("<H", buf, 70)
        return [_wstr(buf[72:72 + size])]
    # HardwareOEM (32), HardwareModel (32), HardwareRevision (2), ChannelCount (2), then channels of
    # MeasurementUnit (4), ChannelNameSize (2), ChannelName (ChannelNameSize bytes)
    (count,) = struct.unpack_from("<H", buf, 66)
    names, offset = [], 68
    for _ in range(count):
        _unit, size = struct.unpack_from("<IH", buf, offset)
        names.append(_wstr(buf[offset + 6:offset + 6 + size]))
        offset += 6 + size
    return names


def parse_emi_measurement(buf, n_channels):
    """[AbsoluteEnergy in picowatt-hours] per channel (each entry also has a 64-bit timestamp)."""
    return [struct.unpack_from("<QQ", buf, 16 * i)[0] for i in range(n_channels)]


def emi_components(watts):
    """Map EMI channel watts to cpu / gpu / memory. Names as used by Chromium and Firefox."""
    out = {}
    pkg = watts.get("RAPL_Package0_PKG")
    igpu = watts.get("RAPL_Package0_PP1")
    if "RAPL_Package0_PP0" in watts:
        out["cpu"] = watts["RAPL_Package0_PP0"]
    elif "VDDCR_VDD Energy" in watts:  # AMD core rail
        out["cpu"] = watts["VDDCR_VDD Energy"]
    elif pkg is not None:
        out["cpu"] = max(pkg - (igpu or 0.0), 0.0)
    else:
        for name in ("Current Socket Energy", "Apu Energy"):  # AMD whole package
            if name in watts:
                out["cpu"] = watts[name]
                break
    if igpu is not None:
        out["gpu"] = igpu
    if "RAPL_Package0_DRAM" in watts:
        out["memory"] = watts["RAPL_Package0_DRAM"]
    return out


class EnergyMeters:
    """All EMI devices on this PC. watts() gives average watts per channel since the last call."""

    def __init__(self):
        from ctypes import wintypes as wt

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wt.DWORD),
                        ("Reserved", ctypes.c_size_t)]

        setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        V = ctypes.c_void_p
        setupapi.SetupDiGetClassDevsW.restype = V
        setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
        setupapi.SetupDiEnumDeviceInterfaces.argtypes = [V, V, ctypes.POINTER(GUID), wt.DWORD,
                                                         ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
        setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [V, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), V,
                                                              wt.DWORD, ctypes.POINTER(wt.DWORD), V]
        setupapi.SetupDiDestroyDeviceInfoList.argtypes = [V]
        kernel32.CreateFileW.restype = V
        kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, V, wt.DWORD, wt.DWORD, V]
        kernel32.DeviceIoControl.argtypes = [V, wt.DWORD, V, wt.DWORD, V, wt.DWORD, ctypes.POINTER(wt.DWORD), V]
        kernel32.CloseHandle.argtypes = [V]
        self._k32 = kernel32

        guid = GUID(EMI_GUID[0], EMI_GUID[1], EMI_GUID[2], (ctypes.c_ubyte * 8)(*EMI_GUID[3]))
        invalid = ctypes.c_void_p(-1).value
        devs = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x2 | 0x10)  # PRESENT | DEVICEINTERFACE
        if not devs or devs == invalid:
            raise OSError("no energy meter devices")
        self.devices = []  # (handle, channel names, measurement buffer size)
        try:
            index = 0
            while True:
                iface = SP_DEVICE_INTERFACE_DATA(cbSize=ctypes.sizeof(SP_DEVICE_INTERFACE_DATA))
                if not setupapi.SetupDiEnumDeviceInterfaces(devs, None, ctypes.byref(guid), index, ctypes.byref(iface)):
                    break
                index += 1
                needed = wt.DWORD()
                setupapi.SetupDiGetDeviceInterfaceDetailW(devs, ctypes.byref(iface), None, 0, ctypes.byref(needed), None)
                detail = ctypes.create_string_buffer(needed.value)
                # cbSize of SP_DEVICE_INTERFACE_DETAIL_DATA_W: 8 on 64-bit Python, 6 on 32-bit
                struct.pack_into("<I", detail, 0, 8 if ctypes.sizeof(V) == 8 else 6)
                if not setupapi.SetupDiGetDeviceInterfaceDetailW(devs, ctypes.byref(iface), detail, needed,
                                                                 None, None):
                    continue
                path = ctypes.wstring_at(ctypes.addressof(detail) + 4)
                handle = kernel32.CreateFileW(path, 0x80000000, 0x3, None, 3, 0x80, None)  # GENERIC_READ, OPEN_EXISTING
                if not handle or handle == invalid:
                    continue
                names = self._channel_names(handle)
                if names:
                    self.devices.append((handle, names))
                else:
                    kernel32.CloseHandle(handle)
        finally:
            setupapi.SetupDiDestroyDeviceInfoList(devs)
        if not self.devices:
            raise OSError("no readable energy meter channels")
        self._last = None  # (time, {channel: picowatt-hours})
        self.watts()  # first reading, so the next one has something to subtract from

    def _ioctl(self, handle, code, size):
        from ctypes import wintypes as wt
        buf, got = ctypes.create_string_buffer(size), wt.DWORD()
        if not self._k32.DeviceIoControl(handle, code, None, 0, buf, size, ctypes.byref(got), None):
            return None
        return buf.raw[:got.value]

    def _channel_names(self, handle):
        version = self._ioctl(handle, IOCTL_EMI_GET_VERSION, 2)
        size = self._ioctl(handle, IOCTL_EMI_GET_METADATA_SIZE, 4)
        if not version or not size:
            return None
        (version,), (size,) = struct.unpack("<H", version[:2]), struct.unpack("<I", size[:4])
        meta = self._ioctl(handle, IOCTL_EMI_GET_METADATA, size)
        if version not in (1, 2) or not meta:
            return None
        return parse_emi_metadata(version, meta)

    def channel_names(self):
        return [n for _, names in self.devices for n in names]

    def watts(self):
        now, totals = time.monotonic(), {}
        for handle, names in self.devices:
            raw = self._ioctl(handle, IOCTL_EMI_GET_MEASUREMENT, 16 * len(names))
            if raw and len(raw) >= 16 * len(names):
                totals.update(zip(names, parse_emi_measurement(raw, len(names))))
        last, self._last = self._last, (now, totals)
        if not last or now <= last[0]:
            return {}
        dt = now - last[0]
        return {name: (pwh - last[1][name]) * JOULES_PER_PICOWATT_HOUR / dt
                for name, pwh in totals.items() if name in last[1] and pwh >= last[1][name]}


# --- Battery ----------------------------------------------------------------
BATTERY_UNKNOWN_RATE = -0x80000000


def battery_watts():
    """Whole-laptop power while running on battery (Rate is negative mW when discharging)."""
    from ctypes import wintypes as wt

    class SYSTEM_BATTERY_STATE(ctypes.Structure):
        _fields_ = [("AcOnLine", ctypes.c_ubyte), ("BatteryPresent", ctypes.c_ubyte),
                    ("Charging", ctypes.c_ubyte), ("Discharging", ctypes.c_ubyte),
                    ("Spare1", ctypes.c_ubyte * 3), ("Tag", ctypes.c_ubyte),
                    ("MaxCapacity", wt.DWORD), ("RemainingCapacity", wt.DWORD), ("Rate", ctypes.c_long),
                    ("EstimatedTime", wt.DWORD), ("DefaultAlert1", wt.DWORD), ("DefaultAlert2", wt.DWORD)]

    state = SYSTEM_BATTERY_STATE()
    status = ctypes.WinDLL("powrprof").CallNtPowerInformation(5, None, 0, ctypes.byref(state), ctypes.sizeof(state))
    if status != 0 or not state.BatteryPresent or not state.Discharging:
        return None
    if state.Rate >= 0 or state.Rate == BATTERY_UNKNOWN_RATE:
        return None
    return -state.Rate / 1000


# --- GPU utilization --------------------------------------------------------
GPU_3D_COUNTER = r"\GPU Engine(*engtype_3D)\Utilization Percentage"


class GpuCounters:
    """Total 3D-engine utilization across all processes, from Windows performance counters."""

    PDH_FMT_DOUBLE = 0x200
    PDH_MORE_DATA = 0x800007D2

    def __init__(self):
        from ctypes import wintypes as wt

        class FMT_VALUE(ctypes.Structure):
            _fields_ = [("CStatus", wt.DWORD), ("doubleValue", ctypes.c_double)]

        class FMT_ITEM(ctypes.Structure):
            _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", FMT_VALUE)]

        self._item = FMT_ITEM
        self.pdh = ctypes.WinDLL("pdh")
        self.query, self.counter = ctypes.c_void_p(), ctypes.c_void_p()
        if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.query)) != 0:
            raise OSError("PdhOpenQuery failed")
        if self.pdh.PdhAddEnglishCounterW(self.query, GPU_3D_COUNTER, None, ctypes.byref(self.counter)) != 0:
            raise OSError("GPU Engine counters not available")
        self.pdh.PdhCollectQueryData(self.query)  # rate counters need a first sample

    def percent(self):
        from ctypes import wintypes as wt
        if self.pdh.PdhCollectQueryData(self.query) != 0:
            return None
        size, count = wt.DWORD(0), wt.DWORD(0)
        status = self.pdh.PdhGetFormattedCounterArrayW(self.counter, self.PDH_FMT_DOUBLE, ctypes.byref(size),
                                                       ctypes.byref(count), None)
        if status & 0xFFFFFFFF != self.PDH_MORE_DATA:
            return 0.0  # no GPU engine instances right now
        buf = ctypes.create_string_buffer(size.value)
        if self.pdh.PdhGetFormattedCounterArrayW(self.counter, self.PDH_FMT_DOUBLE, ctypes.byref(size),
                                                 ctypes.byref(count), buf) != 0:
            return None
        items = ctypes.cast(buf, ctypes.POINTER(self._item))
        total = sum(items[i].FmtValue.doubleValue for i in range(count.value) if items[i].FmtValue.CStatus in (0, 1))
        return min(total, 100.0)


class WindowsSensors:
    def __init__(self):
        self.meters = self._try(EnergyMeters)
        self.gpu = self._try(GpuCounters)
        self.channels = self.meters.channel_names() if self.meters else []

    @staticmethod
    def _try(cls):
        try:
            return cls()
        except (OSError, AttributeError, ValueError):
            return None

    def sources(self):
        found = emi_components({name: 0.0 for name in self.channels})
        return {
            "system": "battery (CallNtPowerInformation)",
            "cpu": "EMI (RAPL)" if "cpu" in found else None,
            "gpu": "EMI (RAPL PP1)" if "gpu" in found else None,
            "memory": "EMI (RAPL DRAM)" if "memory" in found else None,
            "disk": None,
        }

    def system_power(self):
        try:
            watts = battery_watts()
        except (OSError, AttributeError):
            return None
        return {"watts": watts} if watts is not None else None

    def gpu_percent(self):
        try:
            return self.gpu.percent() if self.gpu else None
        except OSError:
            return None

    def read_components(self):
        if not self.meters:
            return {}
        try:
            return emi_components(self.meters.watts())
        except OSError:
            return {}
