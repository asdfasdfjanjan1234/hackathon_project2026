"""Wall-meter checks: our whole-machine readings against a plug-in meter."""

import time
from contextlib import closing

import pytest

from app import create_app
from app.services import storage, validation

MAC = {"machine_id": "MAC-1", "hostname": "test-mac", "os": "macos"}


def add_samples(conn, device, start, seconds, watts, measured=True, step=2.0):
    t = start
    while t < start + seconds:
        t += step
        storage.save_sample(conn, t, step, 20.0, 0.0, watts * 0.8, watts if measured else None, [],
                            device_id=device)


@pytest.fixture
def conn(tmp_path):
    with closing(storage.connect(str(tmp_path / "v.db"))) as c:
        yield c


def test_machine_energy_uses_sensor_watts_and_reports_coverage(conn):
    device = storage.register_device(conn, MAC)
    add_samples(conn, device, 1000, 1800, 20.0)  # half an hour at 20 W
    e = storage.machine_energy(conn, 1000, 4600, device)  # over an hour
    assert e["kwh"] == pytest.approx(0.01)
    assert e["avg_watts"] == pytest.approx(20.0)
    assert e["coverage"] == pytest.approx(0.5)
    assert e["measured_share"] == 1.0


def test_spot_check_compares_meter_with_recent_average(conn):
    device = storage.register_device(conn, MAC)
    now = time.time()
    add_samples(conn, device, now - 40, 40, 20.0)
    validation.spot_check(conn, device, 22.0, now=now + 0.5)
    check = validation.describe(storage.meter_checks(conn, device)[0])
    assert check["app"] == pytest.approx(20.0)
    assert check["difference_pct"] == pytest.approx(-9.1)


def test_spot_check_needs_the_device_reader(conn):
    with pytest.raises(validation.CheckError):
        validation.spot_check(conn, None, 20.0)
    device = storage.register_device(conn, MAC)
    now = time.time()
    add_samples(conn, device, now - 6, 6, 20.0)  # reader just started
    with pytest.raises(validation.CheckError, match="needs 30 s"):
        validation.spot_check(conn, device, 20.0, now=now + 0.5)


def test_kwh_window_check(conn):
    device = storage.register_device(conn, MAC)
    validation.start_window(conn, device, 100.00, now=1000)
    with pytest.raises(validation.CheckError):
        validation.start_window(conn, device, 100.00, now=1001)  # one at a time
    add_samples(conn, device, 1000, 3600, 100.0, measured=False)  # an hour at 100 W, estimated
    validation.finish_window(conn, device, 100.11, now=4600)
    check = validation.describe(storage.meter_checks(conn, device)[0])
    assert check["meter"] == pytest.approx(0.11)
    assert check["app"] == pytest.approx(0.08)  # the formula's estimate: 80 W
    assert check["difference_pct"] == pytest.approx(-27.3)
    assert validation.summary([check]) == {"checks": 1, "mean_abs_difference_pct": 27.3, "worst_pct": 27.3}


def test_kwh_window_without_readings_is_discarded(conn):
    device = storage.register_device(conn, MAC)
    validation.start_window(conn, device, 5.0, now=1000)
    add_samples(conn, device, 1000, 600, 50.0)  # reader ran 10 of 60 minutes
    with pytest.raises(validation.CheckError, match="discarded"):
        validation.finish_window(conn, device, 5.05, now=4600)
    assert storage.meter_checks(conn, device) == []


def test_validation_api(tmp_path):
    app = create_app()
    app.config.update(TESTING=True, DATABASE=str(tmp_path / "api.db"))
    client = app.test_client()
    assert client.get("/api/validation").json["summary"]["checks"] == 0
    assert client.post("/api/validation/watts", json={"value": "abc"}).status_code == 400
    assert client.post("/api/validation/watts", json={"value": 20}).status_code == 409  # no readings
    started = client.post("/api/validation/start", json={"value": 12.5}).json
    assert started["running"]["kind"] == "kwh"
    assert client.post("/api/validation/finish", json={"value": 12.0}).status_code == 409  # below start
    assert client.delete(f"/api/validation/{started['running']['id']}").json["running"] is None
