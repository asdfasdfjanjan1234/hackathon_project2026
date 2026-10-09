"""Detects the operating system and the devices in this computer, once, before any readings.

Python libraries do the cross-platform part:
  platform   OS name, version and architecture
  psutil     CPU cores and clock, RAM size, battery
  shutil     whether nvidia-smi is installed
Each OS's own hardware report fills in the rest, in a single call at startup:
  macOS      system_profiler -json   model, chip, GPU cores, displays, NVMe SSDs, battery health
  Windows    PowerShell CIM queries  model and form factor, CPU, GPUs, NPUs, disks, displays
  Linux      sysfs and /proc         model and chassis, CPU, GPUs (lspci), NPUs, disks, displays, battery health

The collector uses the result to pick sensors (measurement.py) and to size estimates,
e.g. disk power depends on whether the disk is an NVMe SSD, a SATA SSD or a hard drive.
"""

import glob
import json
import os
import platform
import re
import shutil
import subprocess
import uuid

import psutil

WINDOWS_INVENTORY = r"""
$ErrorActionPreference = 'SilentlyContinue'
[pscustomobject]@{
  system   = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, PCSystemType
  cpu      = @(Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed)
  gpus     = @(Get-CimInstance Win32_VideoController | Select-Object Name, AdapterCompatibility, AdapterRAM)
  npus     = @(Get-CimInstance Win32_PnPEntity -Filter "PNPClass='ComputeAccelerator'" | Select-Object Name)
  disks    = @(Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, Size)
  displays = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorConnectionParams | Select-Object VideoOutputTechnology)
} | ConvertTo-Json -Depth 4 -Compress
"""


def _run(cmd, timeout=20):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _gb(n_bytes):
    return round(n_bytes / 1e9) if n_bytes else None


# --- macOS ------------------------------------------------------------------

def parse_system_profiler(data):
    """Devices from `system_profiler -json SPHardwareDataType SPDisplaysDataType SPNVMeDataType SPPowerDataType`."""
    hw = (data.get("SPHardwareDataType") or [{}])[0]
    name = hw.get("machine_name", "Mac")
    out = {
        "device": {
            "type": "laptop" if "MacBook" in name else "desktop",
            "manufacturer": "Apple",
            "model": f"{name} ({hw['machine_model']})" if hw.get("machine_model") else name,
        },
        "gpus": [], "displays": [], "disks": [],
    }
    if hw.get("chip_type"):
        out["cpu"] = hw["chip_type"]
    for gpu in data.get("SPDisplaysDataType", []):
        if gpu.get("sppci_device_type") == "spdisplays_gpu":
            vram = gpu.get("spdisplays_vram") or gpu.get("_spdisplays_vram")
            out["gpus"].append({
                "name": gpu.get("sppci_model") or gpu.get("_name"),
                "type": "integrated" if gpu.get("sppci_bus") == "spdisplays_builtin" else "discrete",
                "cores": int(gpu["sppci_cores"]) if str(gpu.get("sppci_cores", "")).isdigit() else None,
                "vram": vram,
            })
        for disp in gpu.get("spdisplays_ndrvs", []):
            out["displays"].append({
                "name": disp.get("_name"),
                "built_in": disp.get("spdisplays_connection_type") == "spdisplays_internal",
                "resolution": disp.get("_spdisplays_resolution"),
            })
    for controller in data.get("SPNVMeDataType", []):
        for disk in controller.get("_items", []):
            out["disks"].append({"name": disk.get("device_model") or disk.get("_name"), "type": "nvme",
                                 "size_gb": _gb(disk.get("size_in_bytes"))})
    for entry in data.get("SPPowerDataType", []):
        health = entry.get("sppower_battery_health_info")
        if health:
            out["battery_health"] = {"max_capacity": health.get("sppower_battery_health_maximum_capacity"),
                                     "cycles": health.get("sppower_battery_cycle_count")}
    return out


def _macos_devices(apple_silicon):
    raw = _run(["system_profiler", "-json", "-detailLevel", "mini",
                "SPHardwareDataType", "SPDisplaysDataType", "SPNVMeDataType", "SPPowerDataType"])
    try:
        out = parse_system_profiler(json.loads(raw)) if raw else {}
    except (ValueError, KeyError, TypeError):
        out = {}
    if apple_silicon:
        out["npus"] = [{"name": "Apple Neural Engine"}]
    return out


# --- Windows ----------------------------------------------------------------

MEDIA_TYPES = {3: "hdd", 4: "ssd", 5: "scm", "HDD": "hdd", "SSD": "ssd", "SCM": "scm"}
NVME_BUS = (17, "NVMe")
USB_BUS = (7, "USB")
VOT_INTERNAL = 0x80000000  # VideoOutputTechnology of a built-in panel


def _gpu_type(name):
    lowered = name.lower()
    discrete = ("nvidia" in lowered or "radeon rx" in lowered or "radeon pro" in lowered or "arc a" in lowered)
    return "discrete" if discrete else "integrated"


def parse_windows_inventory(data):
    """Devices from the WINDOWS_INVENTORY PowerShell script's JSON."""
    system = data.get("system") or {}
    cpus = _as_list(data.get("cpu"))
    out = {
        # PCSystemType 2 is "Mobile", Windows' name for laptops and tablets.
        "device": {"type": "laptop" if system.get("PCSystemType") == 2 else "desktop",
                   "manufacturer": (system.get("Manufacturer") or "").strip() or None,
                   "model": (system.get("Model") or "").strip() or None},
        "gpus": [], "npus": [], "disks": [], "displays": [],
    }
    if cpus and cpus[0].get("Name"):
        out["cpu"] = cpus[0]["Name"].strip()
        out["cpu_max_mhz"] = cpus[0].get("MaxClockSpeed")
    for gpu in _as_list(data.get("gpus")):
        name = (gpu.get("Name") or "").strip()
        if not name or "basic display" in name.lower() or "remote" in name.lower():
            continue
        out["gpus"].append({"name": name, "type": _gpu_type(name), "cores": None,
                            # AdapterRAM is a 32-bit field, so it tops out at 4 GB.
                            "vram": f"{_gb(gpu['AdapterRAM'])} GB" if gpu.get("AdapterRAM") else None})
    out["npus"] = [{"name": n["Name"].strip()} for n in _as_list(data.get("npus")) if n.get("Name")]
    for disk in _as_list(data.get("disks")):
        bus, media = disk.get("BusType"), MEDIA_TYPES.get(disk.get("MediaType"), "unknown")
        kind = "nvme" if bus in NVME_BUS else media
        out["disks"].append({"name": (disk.get("FriendlyName") or "").strip(), "type": kind,
                             "size_gb": _gb(disk.get("Size")), "external": bus in USB_BUS})
    for disp in _as_list(data.get("displays")):
        tech = disp.get("VideoOutputTechnology")
        built_in = tech is not None and (int(tech) & 0xFFFFFFFF) == VOT_INTERNAL
        out["displays"].append({"name": "Built-in display" if built_in else "External display", "built_in": built_in})
    return out


def _windows_devices():
    raw = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_INVENTORY], timeout=30)
    try:
        return parse_windows_inventory(json.loads(raw)) if raw else {}
    except (ValueError, KeyError, TypeError, AttributeError):
        return {}


# --- Linux ------------------------------------------------------------------

# DMI chassis types of portable machines: Portable, Laptop, Notebook, Hand Held, Sub Notebook,
# Tablet, Convertible, Detachable.
LAPTOP_CHASSIS = {8, 9, 10, 11, 14, 30, 31, 32}
PCI_VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel"}
NPU_DRIVERS = {"intel_vpu": "Intel NPU", "amdxdna": "AMD Ryzen AI NPU"}
VIRTUAL_DISKS = ("loop", "ram", "zram", "dm-", "md", "sr", "fd")


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def parse_lspci(text):
    """GPUs from `lspci -mm` lines whose class is a display controller."""
    gpus = []
    for line in text.splitlines():
        fields = re.findall(r'"([^"]*)"', line)
        if len(fields) >= 3 and any(k in fields[0] for k in ("VGA", "3D controller", "Display controller")):
            vendor, device = fields[1], fields[2]
            name = f"{vendor.split()[0]} {device}".strip()
            kind = "integrated" if vendor.startswith("Intel") and "Arc A" not in device else _gpu_type(name)
            gpus.append({"name": name, "type": kind, "cores": None, "vram": None})
    return gpus


def _linux_cpu(root):
    info = _read(os.path.join(root, "proc", "cpuinfo"))
    for key in ("model name", "Model", "Hardware"):
        m = re.search(rf"^{key}\s*:\s*(.+)$", info, re.M)
        if m:
            return m.group(1).strip()
    return None


def _linux_gpus(root):
    gpus = parse_lspci(_run(["lspci", "-mm"])) if root == "/" and shutil.which("lspci") else []
    if gpus:
        return gpus
    for dev in sorted(glob.glob(os.path.join(root, "sys", "class", "drm", "card[0-9]", "device"))):
        vendor = PCI_VENDORS.get(_read(os.path.join(dev, "vendor")))
        if vendor:
            gpus.append({"name": f"{vendor} GPU", "type": "integrated" if vendor == "Intel" else "discrete",
                         "cores": None, "vram": None})
    return gpus


def _linux_disks(root):
    disks = []
    for block in sorted(glob.glob(os.path.join(root, "sys", "block", "*"))):
        name = os.path.basename(block)
        if name.startswith(VIRTUAL_DISKS):
            continue
        rotational = _read(os.path.join(block, "queue", "rotational")) == "1"
        kind = "nvme" if name.startswith("nvme") else "hdd" if rotational else "ssd"
        sectors = _read(os.path.join(block, "size"))
        disks.append({"name": _read(os.path.join(block, "device", "model")) or name, "type": kind,
                      "size_gb": _gb(int(sectors) * 512) if sectors.isdigit() else None,
                      "external": _read(os.path.join(block, "removable")) == "1"})
    return disks


def _linux_displays(root):
    out = []
    for conn in sorted(glob.glob(os.path.join(root, "sys", "class", "drm", "card*-*"))):
        if _read(os.path.join(conn, "status")) != "connected":
            continue
        port = os.path.basename(conn).split("-", 1)[1]
        built_in = port.startswith(("eDP", "LVDS", "DSI"))
        out.append({"name": "Built-in display" if built_in else f"External display ({port})", "built_in": built_in})
    return out


def _linux_npus(root):
    npus = []
    for dev in sorted(glob.glob(os.path.join(root, "sys", "class", "accel", "accel*", "device", "driver"))):
        driver = os.path.basename(os.path.realpath(dev))
        if driver in NPU_DRIVERS:
            npus.append({"name": NPU_DRIVERS[driver]})
    return npus


def linux_devices(root="/"):
    """Devices from sysfs and /proc (plus `lspci` for GPU names when installed)."""
    from .sensors_linux import battery_health

    dmi = os.path.join(root, "sys", "class", "dmi", "id")
    chassis = _read(os.path.join(dmi, "chassis_type"))
    vendor, product = _read(os.path.join(dmi, "sys_vendor")), _read(os.path.join(dmi, "product_name"))
    out = {"gpus": _linux_gpus(root), "npus": _linux_npus(root), "disks": _linux_disks(root),
           "displays": _linux_displays(root), "device": {"manufacturer": vendor or None, "model": product or None}}
    if chassis.isdigit():
        out["device"]["type"] = "laptop" if int(chassis) in LAPTOP_CHASSIS else "desktop"
    cpu = _linux_cpu(root)
    if cpu:
        out["cpu"] = cpu
    health = battery_health(root)
    if health:
        out["battery_health"] = health
    return out


# --- Any OS -----------------------------------------------------------------

def _nvidia_gpus():
    raw = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], timeout=10)
    gpus = []
    for line in raw.splitlines():
        name, _, mib = line.partition(",")
        if name.strip():
            gpus.append({"name": name.strip(), "type": "discrete", "cores": None,
                         "vram": f"{round(float(mib) / 1024)} GB" if mib.strip().replace(".", "").isdigit() else None})
    return gpus


def detect_system():
    system = platform.system()
    os_name = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(system, system.lower())
    arch = platform.machine().lower()
    apple_silicon = os_name == "macos" and arch == "arm64"
    try:
        battery = psutil.sensors_battery()
    except (AttributeError, NotImplementedError, OSError):
        battery = None
    freq = psutil.cpu_freq() if hasattr(psutil, "cpu_freq") else None

    info = {
        "machine_id": machine_id(os_name),
        "hostname": platform.node(),
        "os": os_name,
        "os_version": platform.mac_ver()[0] if os_name == "macos" else platform.version(),
        "arch": arch,
        "cpu": platform.processor() or arch,
        "cpu_cores": {"physical": psutil.cpu_count(logical=False), "logical": psutil.cpu_count()},
        "cpu_max_mhz": round(freq.max) if freq and freq.max else None,
        "apple_silicon": apple_silicon,
        "memory_gb": round(psutil.virtual_memory().total / 1024 ** 3, 1),
        "device": {"type": "laptop" if battery is not None else "desktop", "manufacturer": None, "model": None},
        "gpus": [], "npus": [], "disks": [], "displays": [],
        "has_battery": battery is not None,
        "on_battery": battery is not None and not battery.power_plugged,
        "battery": {"percent": round(battery.percent), "plugged_in": bool(battery.power_plugged)} if battery else None,
        "nvidia_gpu": shutil.which("nvidia-smi") is not None,
    }
    if os_name == "macos":
        found = _macos_devices(apple_silicon)
    elif os_name == "windows":
        found = _windows_devices()
    elif os_name == "linux":
        found = linux_devices()
    else:
        found = {}
    health = found.pop("battery_health", None)
    if health and info["battery"]:
        info["battery"].update(health)
    device = {k: v for k, v in (found.pop("device", None) or {}).items() if v}
    info["device"].update(device)
    info.update({k: v for k, v in found.items() if v not in (None, [], "")})
    if info["nvidia_gpu"]:
        known = {g["name"] for g in info["gpus"]}
        info["gpus"] += [g for g in _nvidia_gpus() if g["name"] not in known]
    return info


def machine_id(os_name):
    """An ID that stays the same for this computer, so its readings are stored under one device."""
    if os_name == "macos":
        m = re.search(r'"IOPlatformUUID" = "([^"]+)"', _run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]))
        if m:
            return m.group(1)
    elif os_name == "windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                return winreg.QueryValueEx(key, "MachineGuid")[0]
        except OSError:
            pass
    elif os_name == "linux":
        try:
            with open("/etc/machine-id") as f:
                return f.read().strip()
        except OSError:
            pass
    return f"{platform.node()}-{uuid.getnode():012x}"
