"""Storage runs the same on SQLite and MySQL. The MySQL cases run when TEST_DATABASE_URL is set, e.g.

    TEST_DATABASE_URL=mysql://root:secret@127.0.0.1:3306/ai_wattage_test pytest tests/test_storage.py

That database is emptied before each test.
"""

import os
import sqlite3
import time
from contextlib import closing

import pytest

from app import create_app
from app.services import storage
from app.services.attribution import PowerModel

MYSQL_URL = os.getenv("TEST_DATABASE_URL")
MAC = {"machine_id": "MAC-1", "hostname": "marias-mac", "os": "macos", "os_version": "26.4", "arch": "arm64",
       "cpu": "Apple M2", "memory_gb": 16.0, "device": {"model": "MacBook Air (Mac14,2)"}}
PC = {"machine_id": "PC-1", "hostname": "johns-pc", "os": "windows", "cpu": "AMD Ryzen 9", "device": {}}
APP = {"app": "Ollama", "model": "Ollama · llama3:8b", "kind": "local", "cpu_percent": 100, "rss_mb": 5000}


@pytest.fixture(params=["sqlite", pytest.param("mysql", marks=pytest.mark.skipif(
    not MYSQL_URL, reason="set TEST_DATABASE_URL to a MySQL test database"))])
def database(request, tmp_path):
    if request.param == "sqlite":
        return str(tmp_path / "t.db")
    with closing(storage.connect(MYSQL_URL)) as conn:
        for table in (*storage.READING_TABLES, "meter_checks", "settings", "devices"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    return MYSQL_URL


def test_devices_are_registered_once_and_tag_their_readings(database):
    with closing(storage.connect(database)) as conn:
        mac = storage.register_device(conn, MAC)
        pc = storage.register_device(conn, PC)
        assert storage.register_device(conn, {**MAC, "hostname": "renamed"}) == mac != pc
        now = time.time()
        for i in range(3):
            storage.save_sample(conn, now - i, 2, 40, 10, 9.5, None, [{**APP, "watts": 3.0}],
                                {"cpu": {"watts": 5.0, "source": "estimated"}}, device_id=mac)
        storage.save_sample(conn, now, 2, 5, 0, 30.0, 28.0, [], device_id=pc)

        found = {d["id"]: d for d in storage.list_devices(conn)}
        assert found[mac]["name"] == "renamed" and found[mac]["model"] == "MacBook Air (Mac14,2)"
        assert found[mac]["samples"] == 3 and found[pc]["samples"] == 1
        assert found[mac]["last_seen"] == pytest.approx(now)

        rows = storage.readings(conn, device_id=mac)
        assert [r["ts"] for r in rows] == pytest.approx([now, now - 1, now - 2])
        assert rows[0]["components"] == {"cpu": {"watts": 5.0, "source": "estimated"}}
        assert rows[0]["apps"][0]["model"] == "Ollama · llama3:8b" and rows[0]["apps"][0]["watts"] == 3.0
        assert len(storage.readings(conn)) == 4 and len(storage.readings(conn, since=now - 0.5)) == 2


def test_daily_usage_and_power_model_round_trip(database):
    with closing(storage.connect(database)) as conn:
        for i in range(10):  # 10 samples × 360 s × 100 W = 100 Wh
            storage.save_sample(conn, time.time() - i, 360, 50, 20, 30, None, [{**APP, "watts": 100}],
                                {"gpu": {"watts": 10.0, "source": "IOReport"}})
        (row,) = storage.daily_usage(conn)
        assert row["kwh"] == pytest.approx(0.1) and row["date"] == time.strftime("%Y-%m-%d")
        (part,) = storage.daily_component_usage(conn)
        assert part["kwh"] == pytest.approx(0.01) and part["measured_share"] == 1.0
        assert storage.host_usage(conn)[0]["host"] == "standalone"
        assert storage.sample_count(conn) == 10

        storage.save_window(conn, time.time(), 10.0, 30.0, 0.0, 5)
        assert storage.recent_windows(conn) == [(10.0, 30.0, 0.0)]
        storage.set_power_model(conn, PowerModel(idle_watts=4.0))
        storage.set_power_model(conn, PowerModel(idle_watts=5.0))
        assert storage.get_power_model(conn).idle_watts == 5.0


def test_readings_and_devices_endpoints(database):
    with closing(storage.connect(database)) as conn:
        device = storage.register_device(conn, MAC)
        storage.save_sample(conn, time.time(), 2, 30, 10, 8, 7.5, [], device_id=device)
    flask_app = create_app()
    flask_app.config.update(TESTING=True, DATABASE=database)
    client = flask_app.test_client()
    body = client.get("/api/devices").json
    assert body["database"] == ("mysql" if storage.is_mysql(database) else "sqlite")
    assert body["devices"][0]["name"] == "marias-mac"
    body = client.get(f"/api/readings?device_id={device}&limit=10").json
    assert body["count"] == 1 and body["readings"][0]["measured_watts"] == 7.5


def test_old_sqlite_databases_get_device_columns(tmp_path):
    path = str(tmp_path / "old.db")
    with closing(sqlite3.connect(path)) as raw:
        raw.execute("CREATE TABLE samples (ts REAL, interval_s REAL, cpu_percent REAL, gpu_percent REAL, "
                    "est_watts REAL, measured_watts REAL)")
        raw.execute("INSERT INTO samples VALUES (1, 2, 3, 4, 5, 6)")
        raw.commit()
    with closing(storage.connect(path)) as conn:
        assert storage.readings(conn)[0]["device_id"] is None


def test_password_is_hidden_when_printed():
    assert storage.describe("mysql://wattage:s3cret@localhost/ai_wattage") == "mysql://wattage@localhost:3306/ai_wattage"


def test_app_parts_are_stored_and_summed(database):
    now = time.time()
    parts = {"cpu_watts": 2.0, "gpu_watts": 6.0, "memory_watts": 1.0, "gpu_share": 1.0, "vram_mb": 4800.0,
             "model_mb": 4800.0}
    with closing(storage.connect(database)) as conn:
        mac = storage.register_device(conn, MAC)
        storage.save_sample(conn, now - 10, 3600, 40, 60, 12, None, [{**APP, "watts": 5.0}], device_id=mac)  # before the split
        storage.save_sample(conn, now, 3600, 40, 60, 12, 11.0, [{**APP, **parts, "watts": 9.0}], device_id=mac)
        (row,) = storage.app_part_usage(conn, device_id=mac)
        latest = storage.latest_sample(conn)
        stored = storage.readings(conn, device_id=mac)
    assert row == {"model": "Ollama · llama3:8b", "cpu_kwh": 0.002, "gpu_kwh": 0.006, "memory_kwh": 0.001,
                   "unsplit_kwh": 0.005}
    assert {k: latest["apps"][0][k] for k in parts} == parts
    assert stored[0]["apps"][0]["gpu_watts"] == 6.0 and stored[1]["apps"][0]["gpu_watts"] is None


def test_old_sqlite_databases_get_app_part_columns(tmp_path):
    path = str(tmp_path / "old.db")
    with closing(sqlite3.connect(path)) as raw:
        raw.execute("CREATE TABLE ai_samples (ts REAL, interval_s REAL, app TEXT, model TEXT, kind TEXT, "
                    "cpu_percent REAL, rss_mb REAL, watts REAL)")
        raw.commit()
    with closing(storage.connect(path)) as conn:
        storage.save_sample(conn, time.time(), 2, 10, 0, 5, None, [{**APP, "watts": 1.0, "cpu_watts": 1.0}])
        assert storage.app_part_usage(conn)[0]["cpu_kwh"] > 0
