import pytest

from app.services.measurement import estimate_disk_watts
from app.services.system_info import detect_system, parse_system_profiler, parse_windows_inventory

# Trimmed from `system_profiler -json` on our M2 MacBook Air.
MAC_PROFILE = {
    "SPHardwareDataType": [{"chip_type": "Apple M2", "machine_model": "Mac14,2", "machine_name": "MacBook Air",
                            "physical_memory": "16 GB"}],
    "SPDisplaysDataType": [{
        "_name": "Apple M2", "sppci_bus": "spdisplays_builtin", "sppci_cores": "8",
        "sppci_device_type": "spdisplays_gpu", "sppci_model": "Apple M2",
        "spdisplays_ndrvs": [{"_name": "Color LCD", "_spdisplays_resolution": "1710 x 1112 @ 60.00Hz",
                              "spdisplays_connection_type": "spdisplays_internal"}],
    }],
    "SPNVMeDataType": [{"_items": [{"_name": "APPLE SSD AP0256Z", "device_model": "APPLE SSD AP0256Z",
                                    "size_in_bytes": 251000193024}]}],
    "SPPowerDataType": [{"_name": "spbattery_information", "sppower_battery_health_info": {
        "sppower_battery_cycle_count": 356, "sppower_battery_health_maximum_capacity": "87%"}}],
}

# Shaped like the WINDOWS_INVENTORY script's output on a gaming laptop.
WINDOWS_INVENTORY = {
    "system": {"Manufacturer": "ASUSTeK COMPUTER INC.", "Model": "ROG Zephyrus G14", "PCSystemType": 2},
    "cpu": {"Name": "AMD Ryzen 9 8945HS w/ Radeon 780M Graphics  ", "NumberOfCores": 8, "MaxClockSpeed": 4000},
    "gpus": [{"Name": "AMD Radeon(TM) 780M", "AdapterRAM": 536870912},
             {"Name": "NVIDIA GeForce RTX 4060 Laptop GPU", "AdapterRAM": 4293918720},
             {"Name": "Microsoft Basic Display Adapter"}],
    "npus": {"Name": "AMD IPU Device"},
    "disks": [{"FriendlyName": "Micron 2400 NVMe", "MediaType": 4, "BusType": 17, "Size": 1024209543168},
              {"FriendlyName": "WD Elements", "MediaType": "HDD", "BusType": "USB", "Size": 2000398934016}],
    "displays": [{"VideoOutputTechnology": -2147483648}, {"VideoOutputTechnology": 10}],
}


def test_parse_mac_system_profiler():
    found = parse_system_profiler(MAC_PROFILE)
    assert found["device"] == {"type": "laptop", "manufacturer": "Apple", "model": "MacBook Air (Mac14,2)"}
    assert found["cpu"] == "Apple M2"
    assert found["gpus"] == [{"name": "Apple M2", "type": "integrated", "cores": 8, "vram": None}]
    assert found["displays"] == [{"name": "Color LCD", "built_in": True, "resolution": "1710 x 1112 @ 60.00Hz"}]
    assert found["disks"] == [{"name": "APPLE SSD AP0256Z", "type": "nvme", "size_gb": 251}]
    assert found["battery_health"] == {"max_capacity": "87%", "cycles": 356}


def test_parse_mac_desktop_without_battery():
    profile = {"SPHardwareDataType": [{"machine_name": "Mac mini", "machine_model": "Mac14,3"}]}
    found = parse_system_profiler(profile)
    assert found["device"]["type"] == "desktop" and "battery_health" not in found


def test_parse_windows_inventory():
    found = parse_windows_inventory(WINDOWS_INVENTORY)
    assert found["device"] == {"type": "laptop", "manufacturer": "ASUSTeK COMPUTER INC.", "model": "ROG Zephyrus G14"}
    assert found["cpu"] == "AMD Ryzen 9 8945HS w/ Radeon 780M Graphics"
    assert [(g["name"], g["type"]) for g in found["gpus"]] == [
        ("AMD Radeon(TM) 780M", "integrated"), ("NVIDIA GeForce RTX 4060 Laptop GPU", "discrete")]
    assert found["npus"] == [{"name": "AMD IPU Device"}]  # a single object, not a list
    assert [(d["type"], d["external"]) for d in found["disks"]] == [("nvme", False), ("hdd", True)]
    assert [d["built_in"] for d in found["displays"]] == [True, False]


def test_parse_windows_desktop_with_missing_sections():
    found = parse_windows_inventory({"system": {"PCSystemType": 1}})
    assert found["device"]["type"] == "desktop"
    assert found["gpus"] == found["disks"] == found["npus"] == []


def test_disk_estimate_depends_on_detected_disk_type():
    nvme, hdd = [{"type": "nvme"}], [{"type": "hdd"}]
    assert estimate_disk_watts(0, hdd) > 10 * estimate_disk_watts(0, nvme)
    assert estimate_disk_watts(1, nvme + hdd) == pytest.approx(0.05 + 4.0 + 2.95)  # both idle + busiest disk
    assert estimate_disk_watts(0, [{"type": "unknown"}]) == estimate_disk_watts(0, nvme)


def test_detect_system_on_this_machine_has_every_field():
    info = detect_system()
    for key in ("os", "os_version", "arch", "cpu", "cpu_cores", "memory_gb", "device", "gpus", "npus",
                "disks", "displays", "has_battery", "battery", "nvidia_gpu"):
        assert key in info
    assert info["os"] in ("macos", "windows", "linux") and info["memory_gb"] > 0
