import struct
import time

import pytest

from app import create_app
from app.routes import system as system_route
from app.services import storage
from app.services.attribution import PowerModel
from app.services.collector import WINDOW_S, Collector
from app.services.measurement import DERIVED, Sensors, estimate_disk_watts, estimate_memory_watts
from app.services.sensors_macos import parse_powermetrics
from app.services.sensors_windows import (
    JOULES_PER_PICOWATT_HOUR, emi_components, parse_emi_measurement, parse_emi_metadata,
)

MAC = {"os": "macos", "apple_silicon": True, "memory_gb": 8, "nvidia_gpu": False}
WINDOWS = {"os": "windows", "apple_silicon": False, "memory_gb": 16, "nvidia_gpu": False}


class FakePlatform:
    def __init__(self, sources, measured, tel=None):
        self._sources, self._measured, self._tel = sources, measured, tel

    def sources(self):
        return dict(self._sources)

    def system_power(self):
        return self._tel

    def gpu_percent(self):
        return 20.0

    def read_components(self):
        return dict(self._measured)


def test_linux_has_no_platform_sensors_so_everything_is_estimated():
    sensors = Sensors(system={"os": "linux", "memory_gb": 8})
    assert sensors.platform is None
    parts = sensors.components(50, 0, PowerModel())
    assert {k: v["source"] for k, v in parts.items()} == dict.fromkeys(("cpu", "gpu", "memory", "disk"), "estimated")


def test_measured_components_keep_their_sensor_and_the_rest_are_estimated():
    mac = FakePlatform({"system": "battery (ioreg)", "gpu": "IOReport GPU Energy"}, {"gpu": 0.5})
    model = PowerModel(idle_watts=3, watts_per_cpu_pct=0.1, watts_per_gpu_pct=0.2)
    parts = Sensors(system=MAC, platform_sensors=mac).components(40, 10, model, system_watts=10.0)

    assert parts["gpu"] == {"watts": 0.5, "source": "IOReport GPU Energy"}
    assert parts["cpu"]["source"] == parts["memory"]["source"] == "estimated"
    # The fitted CPU term (0.1 W/% × 40% = 4 W) also covers memory traffic: it's split, not counted twice.
    assert parts["cpu"]["watts"] + parts["memory"]["watts"] == pytest.approx(4.0 + estimate_memory_watts(8, 0), abs=1e-3)
    explained = sum(parts[k]["watts"] for k in ("cpu", "gpu", "memory", "disk"))
    assert parts["other"]["watts"] == pytest.approx(10.0 - explained, abs=1e-3)


def test_windows_sources_report_emi_channels():
    win = FakePlatform({"system": "battery (CallNtPowerInformation)", "cpu": "EMI (RAPL)", "memory": "EMI (RAPL DRAM)"},
                       {"cpu": 6.0, "memory": 1.2})
    sensors = Sensors(system=WINDOWS, platform_sensors=win)
    assert sensors.sources() == {"system": "battery (CallNtPowerInformation)", "cpu": "EMI (RAPL)",
                                 "gpu": None, "memory": "EMI (RAPL DRAM)", "disk": None}
    parts = sensors.components(30, 0, PowerModel())
    assert parts["cpu"]["watts"] == 6.0 and parts["memory"]["source"] == "EMI (RAPL DRAM)"
    assert "other" not in parts  # no whole-machine reading on AC power


def _emi_v2_metadata(names):
    buf = "OEM".encode("utf-16-le").ljust(32, b"\0") + "Model".encode("utf-16-le").ljust(32, b"\0")
    buf += struct.pack("<HH", 1, len(names))
    for name in names:
        raw = (name + "\0").encode("utf-16-le")
        buf += struct.pack("<IH", 0, len(raw)) + raw
    return buf


def test_parse_emi_v2_metadata_and_measurements():
    names = ["RAPL_Package0_PKG", "RAPL_Package0_PP0", "RAPL_Package0_DRAM"]
    assert parse_emi_metadata(2, _emi_v2_metadata(names)) == names
    data = b"".join(struct.pack("<QQ", energy, 123) for energy in (10, 20, 30))
    assert parse_emi_measurement(data, 3) == [10, 20, 30]


def test_parse_emi_v1_metadata():
    raw = "RAPL_Package0_PKG\0".encode("utf-16-le")
    buf = struct.pack("<I", 0) + b"\0" * 64 + struct.pack("<HH", 1, len(raw)) + raw
    assert parse_emi_metadata(1, buf) == ["RAPL_Package0_PKG"]


def test_one_watt_for_one_second_in_picowatt_hours():
    assert (1 / 3600 * 1e12) * JOULES_PER_PICOWATT_HOUR == pytest.approx(1.0)


@pytest.mark.parametrize("channels, expected", [
    ({"RAPL_Package0_PKG": 9, "RAPL_Package0_PP0": 6, "RAPL_Package0_PP1": 2, "RAPL_Package0_DRAM": 1},
     {"cpu": 6, "gpu": 2, "memory": 1}),                         # Intel with every domain
    ({"RAPL_Package0_PKG": 9, "RAPL_Package0_PP1": 2}, {"cpu": 7, "gpu": 2}),  # package minus iGPU
    ({"RAPL_Package0_PKG": 9}, {"cpu": 9}),
    ({"VDDCR_VDD Energy": 5, "VDDCR_SOC Energy": 3}, {"cpu": 5}),  # AMD core rail
    ({"Current Socket Energy": 12}, {"cpu": 12}),
    ({}, {}),
])
def test_emi_channels_map_to_components(channels, expected):
    assert emi_components(channels) == expected


def test_parse_powermetrics():
    text = "CPU Power: 1234 mW\nGPU Power: 56 mW\nANE Power: 0 mW\nCombined Power (CPU + GPU + ANE): 1290 mW\n"
    assert parse_powermetrics(text) == {"cpu": 1.234, "gpu": 0.056, "ane": 0.0}


def test_memory_and_disk_estimates_stay_in_range():
    assert estimate_memory_watts(16, 0) < estimate_memory_watts(16, 100) == estimate_memory_watts(16, 250)
    assert estimate_disk_watts(-1) == estimate_disk_watts(0) < estimate_disk_watts(1) == estimate_disk_watts(5)


def test_windows_battery_readings_are_averaged_into_windows(tmp_path):
    conn = storage.connect(str(tmp_path / "t.db"))
    sensors = Sensors(system=WINDOWS, platform_sensors=FakePlatform({}, {}))
    c = Collector(conn, sensors=sensors)
    start = c._window_start
    c._update_telemetry(start + 1, 10, 0, {"watts": 8.0})
    c._update_telemetry(start + WINDOW_S / 2, 30, 0, {"watts": 12.0})
    assert storage.recent_windows(conn) == []
    c._update_telemetry(start + WINDOW_S, 50, 0, {"watts": 10.0})
    assert storage.recent_windows(conn) == [(pytest.approx(10.0), pytest.approx(30.0), 0.0)]


def test_components_are_stored_and_summed_per_day(tmp_path):
    conn = storage.connect(str(tmp_path / "t.db"))
    parts = {"cpu": {"watts": 10.0, "source": "EMI (RAPL)"}, "disk": {"watts": 1.0, "source": "estimated"},
             "other": {"watts": 2.0, "source": DERIVED}}
    for i in range(10):  # 10 × 360 s
        storage.save_sample(conn, time.time() - i, 360, 50, 0, 12, None, [], parts)
    rows = {r["component"]: r for r in storage.daily_component_usage(conn)}
    assert rows["cpu"]["kwh"] == pytest.approx(0.01) and rows["cpu"]["measured_share"] == 1.0
    assert rows["disk"]["kwh"] == pytest.approx(0.001) and rows["disk"]["measured_share"] == 0.0
    assert rows["other"]["measured_share"] == 0.0  # derived, not measured


def test_system_endpoint_reports_detected_os_and_sensors(tmp_path, monkeypatch):
    fake = Sensors(system=WINDOWS, platform_sensors=FakePlatform({"cpu": "EMI (RAPL)"}, {}))
    monkeypatch.setattr(system_route, "default_sensors", lambda: fake)
    flask_app = create_app()
    flask_app.config.update(TESTING=True, DATABASE=str(tmp_path / "t.db"))
    body = flask_app.test_client().get("/api/system").json
    assert body["system"]["os"] == "windows"
    assert body["sensors"]["cpu"] == "EMI (RAPL)" and body["sensors"]["memory"] is None
