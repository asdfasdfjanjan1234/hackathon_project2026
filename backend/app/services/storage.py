"""Database for device readings: MySQL when DATABASE is a mysql:// URL, otherwise a SQLite file.

    mysql://user:password@localhost:3306/ai_wattage   MySQL (tables are created on first connect)
    /path/to/wattage.db                               SQLite (default, used by the tests)

Every reading row carries the device_id of the computer that took it (the `devices` table).
"""

import json
import os
import sqlite3
import time
from urllib.parse import unquote, urlparse

from .attribution import ACTIVE_CPU_PCT, PowerModel, activity
from .measurement import DERIVED

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT, machine_id TEXT UNIQUE NOT NULL, name TEXT,
    os TEXT, os_version TEXT, arch TEXT, model TEXT, cpu TEXT, memory_gb REAL, first_seen REAL
);
CREATE TABLE IF NOT EXISTS samples (
    ts REAL, interval_s REAL, cpu_percent REAL, gpu_percent REAL,
    est_watts REAL, measured_watts REAL, device_id INTEGER
);
CREATE TABLE IF NOT EXISTS ai_samples (
    ts REAL, interval_s REAL, app TEXT, model TEXT, kind TEXT,
    cpu_percent REAL, rss_mb REAL, watts REAL, host TEXT, device_id INTEGER,
    cpu_watts REAL, gpu_watts REAL, memory_watts REAL, gpu_share REAL, vram_mb REAL, model_mb REAL,
    effort TEXT
);
CREATE TABLE IF NOT EXISTS power_windows (
    ts REAL, avg_watts REAL, avg_cpu REAL, avg_gpu REAL, n_samples INTEGER, device_id INTEGER
);
CREATE TABLE IF NOT EXISTS component_samples (
    ts REAL, interval_s REAL, component TEXT, watts REAL, source TEXT, device_id INTEGER
);
CREATE TABLE IF NOT EXISTS settings (`key` TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS meter_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, device_id INTEGER, kind TEXT,
    started_at REAL, ended_at REAL, meter_start REAL, meter_end REAL, app_value REAL, coverage REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
CREATE INDEX IF NOT EXISTS idx_ai_samples_ts ON ai_samples(ts);
CREATE INDEX IF NOT EXISTS idx_component_samples_ts ON component_samples(ts);
"""

MYSQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INT AUTO_INCREMENT PRIMARY KEY, machine_id VARCHAR(128) NOT NULL UNIQUE, name VARCHAR(255),
    os VARCHAR(32), os_version VARCHAR(255), arch VARCHAR(32), model VARCHAR(255), cpu VARCHAR(255),
    memory_gb DOUBLE, first_seen DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS samples (
    id BIGINT AUTO_INCREMENT PRIMARY KEY, device_id INT, ts DOUBLE NOT NULL, interval_s DOUBLE,
    cpu_percent DOUBLE, gpu_percent DOUBLE, est_watts DOUBLE, measured_watts DOUBLE,
    INDEX idx_samples_ts (ts), INDEX idx_samples_device_ts (device_id, ts),
    FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ai_samples (
    id BIGINT AUTO_INCREMENT PRIMARY KEY, device_id INT, ts DOUBLE NOT NULL, interval_s DOUBLE,
    app VARCHAR(255), model VARCHAR(255), kind VARCHAR(32), cpu_percent DOUBLE, rss_mb DOUBLE,
    watts DOUBLE, host VARCHAR(255),
    cpu_watts DOUBLE, gpu_watts DOUBLE, memory_watts DOUBLE, gpu_share DOUBLE, vram_mb DOUBLE, model_mb DOUBLE,
    effort VARCHAR(32),
    INDEX idx_ai_samples_ts (ts), FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS power_windows (
    id BIGINT AUTO_INCREMENT PRIMARY KEY, device_id INT, ts DOUBLE NOT NULL, avg_watts DOUBLE,
    avg_cpu DOUBLE, avg_gpu DOUBLE, n_samples INT,
    INDEX idx_power_windows_ts (ts), FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS component_samples (
    id BIGINT AUTO_INCREMENT PRIMARY KEY, device_id INT, ts DOUBLE NOT NULL, interval_s DOUBLE,
    component VARCHAR(32), watts DOUBLE, source VARCHAR(64),
    INDEX idx_component_samples_ts (ts), FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(64) PRIMARY KEY, value TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS meter_checks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY, device_id INT, kind VARCHAR(16),
    started_at DOUBLE, ended_at DOUBLE, meter_start DOUBLE, meter_end DOUBLE, app_value DOUBLE, coverage DOUBLE,
    FOREIGN KEY (device_id) REFERENCES devices(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

READING_TABLES = ("samples", "ai_samples", "power_windows", "component_samples")
# Per-app parts of `watts`, GPU share and model memory, added after the first databases were created.
APP_PART_COLUMNS = ("cpu_watts", "gpu_watts", "memory_watts", "gpu_share", "vram_mb", "model_mb")
# The reasoning effort a cloud app asks its model for ("low" ... "max"), when its logs say.
APP_COLUMNS = "app, model, kind, host, cpu_percent, rss_mb, watts, effort, " + ", ".join(APP_PART_COLUMNS)


class Database:
    """One connection to SQLite or MySQL. Queries use ? placeholders and rows read like dicts."""

    def __init__(self, raw, dialect):
        self.raw = raw
        self.dialect = dialect

    def execute(self, sql, params=()):
        cur = self.raw.cursor()
        cur.execute(self._sql(sql), params)
        return cur

    def executemany(self, sql, rows):
        rows = list(rows)
        if rows:
            self.raw.cursor().executemany(self._sql(sql), rows)

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()

    def day(self, column="ts"):
        """SQL for the local calendar day of a Unix timestamp column."""
        if self.dialect == "mysql":
            return f"DATE(FROM_UNIXTIME({column}))"  # session time zone is set to local time on connect
        return f"date({column}, 'unixepoch', 'localtime')"

    def hour(self, column="ts"):
        """SQL for the local hour of day (0-23) of a Unix timestamp column."""
        if self.dialect == "mysql":
            return f"HOUR(FROM_UNIXTIME({column}))"
        return f"CAST(strftime('%H', {column}, 'unixepoch', 'localtime') AS INTEGER)"

    def slot(self, seconds, column="ts"):
        """SQL for the start (Unix seconds) of the `seconds`-long time slot a timestamp falls in."""
        whole = f"FLOOR({column} / {int(seconds)})" if self.dialect == "mysql" else f"CAST({column} / {int(seconds)} AS INTEGER)"
        return f"{whole} * {int(seconds)}"

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.dialect == "mysql" else sql


def is_mysql(target):
    return str(target).startswith("mysql://")


def describe(target):
    """`target` without its password, for printing."""
    if not is_mysql(target):
        return target
    u = urlparse(target)
    return f"mysql://{u.username or 'root'}@{u.hostname or 'localhost'}:{u.port or 3306}{u.path}"


def connect(target):
    """Open the database at `target` (a SQLite path or a mysql:// URL) and create missing tables."""
    if is_mysql(target):
        return _connect_mysql(target)
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    # The device reader writes from its own thread while requests read, so wait on locks.
    raw = sqlite3.connect(target, timeout=10)
    raw.row_factory = sqlite3.Row
    raw.executescript(SQLITE_SCHEMA)
    # Databases from before the host, device_id, per-app part and effort columns were added.
    for table, column, kind in ([("ai_samples", "host", "TEXT")] + [(t, "device_id", "INTEGER") for t in READING_TABLES]
                                + [("ai_samples", c, "REAL") for c in APP_PART_COLUMNS]
                                + [("ai_samples", "effort", "TEXT")]):
        if column not in {r["name"] for r in raw.execute(f"PRAGMA table_info({table})")}:
            raw.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
    return Database(raw, "sqlite")


def _connect_mysql(url):
    import pymysql

    u = urlparse(url)
    raw = pymysql.connect(
        host=u.hostname or "localhost", port=u.port or 3306,
        user=unquote(u.username or "root"), password=unquote(u.password or ""),
        database=u.path.lstrip("/") or "ai_wattage",
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )
    db = Database(raw, "mysql")
    # Group readings by the day on this computer's clock, as SQLite's 'localtime' does.
    offset = time.localtime().tm_gmtoff
    sign = "+" if offset >= 0 else "-"
    db.execute("SET time_zone = ?", (f"{sign}{abs(offset) // 3600:02d}:{abs(offset) % 3600 // 60:02d}",))
    for statement in filter(str.strip, MYSQL_SCHEMA.split(";")):
        db.execute(statement)
    # Databases from before the per-app part and effort columns were added.
    have = {r["COLUMN_NAME"] for r in db.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?",
        ("ai_samples",))}
    for column, kind in [(c, "DOUBLE") for c in APP_PART_COLUMNS] + [("effort", "VARCHAR(32)")]:
        if column not in have:
            db.execute(f"ALTER TABLE ai_samples ADD COLUMN {column} {kind}")
    db.commit()
    return db


def register_device(conn, system):
    """Add this computer to `devices` (or refresh its details) and return its id."""
    mid = system.get("machine_id") or system.get("hostname") or "unknown"
    details = (system.get("hostname"), system.get("os"), system.get("os_version"), system.get("arch"),
               (system.get("device") or {}).get("model"), system.get("cpu"), system.get("memory_gb"))
    row = conn.execute("SELECT id FROM devices WHERE machine_id = ?", (mid,)).fetchone()
    if row:
        conn.execute("UPDATE devices SET name = ?, os = ?, os_version = ?, arch = ?, model = ?, cpu = ?, "
                     "memory_gb = ? WHERE id = ?", (*details, row["id"]))
        conn.commit()
        return row["id"]
    conn.execute("INSERT INTO devices (machine_id, name, os, os_version, arch, model, cpu, memory_gb, first_seen) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (mid, *details, time.time()))
    conn.commit()
    return conn.execute("SELECT id FROM devices WHERE machine_id = ?", (mid,)).fetchone()["id"]


def list_devices(conn):
    """Every device that has stored readings, with how many and when it last read."""
    rows = conn.execute(
        """
        SELECT d.id, d.name, d.os, d.os_version, d.arch, d.model, d.cpu, d.memory_gb, d.first_seen,
               COUNT(s.ts) AS samples, MAX(s.ts) AS last_seen
        FROM devices d LEFT JOIN samples s ON s.device_id = d.id
        GROUP BY d.id, d.name, d.os, d.os_version, d.arch, d.model, d.cpu, d.memory_gb, d.first_seen
        ORDER BY last_seen DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def save_sample(conn, ts, interval_s, cpu, gpu, est_watts, measured_watts, apps, components=None, device_id=None):
    conn.execute(
        "INSERT INTO samples (ts, interval_s, cpu_percent, gpu_percent, est_watts, measured_watts, device_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, interval_s, cpu, gpu, est_watts, measured_watts, device_id))
    conn.executemany(
        f"INSERT INTO ai_samples (ts, interval_s, device_id, {APP_COLUMNS}) VALUES ({', '.join(['?'] * (11 + len(APP_PART_COLUMNS)))})",
        [(ts, interval_s, device_id, a["app"], a["model"], a["kind"], a.get("host"), a["cpu_percent"], a["rss_mb"],
          a["watts"], a.get("effort"), *(a.get(c) for c in APP_PART_COLUMNS)) for a in apps],
    )
    conn.executemany(
        "INSERT INTO component_samples (ts, interval_s, component, watts, source, device_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(ts, interval_s, name, c["watts"], c["source"], device_id) for name, c in (components or {}).items()],
    )
    conn.commit()


def save_window(conn, ts, avg_watts, avg_cpu, avg_gpu, n_samples, device_id=None):
    conn.execute("INSERT INTO power_windows (ts, avg_watts, avg_cpu, avg_gpu, n_samples, device_id) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (ts, avg_watts, avg_cpu, avg_gpu, n_samples, device_id))
    conn.commit()


def _device_filter(device_id, column="device_id"):
    """SQL condition and parameters limiting rows to one device (all devices when None)."""
    return ("", ()) if device_id is None else (f" AND {column} = ?", (device_id,))


def device_id_for(conn, machine_id):
    """The stored id of the computer with this machine ID, or None if it hasn't taken readings."""
    row = conn.execute("SELECT id FROM devices WHERE machine_id = ?", (machine_id,)).fetchone()
    return row["id"] if row else None


def recent_windows(conn, limit=500, device_id=None):
    where, params = _device_filter(device_id)
    rows = conn.execute(
        f"SELECT avg_watts, avg_cpu, avg_gpu FROM power_windows WHERE 1 = 1{where} ORDER BY ts DESC LIMIT ?",
        (*params, limit),
    ).fetchall()
    return [(r["avg_watts"], r["avg_cpu"], r["avg_gpu"]) for r in rows]


def _power_model_key(device_id):
    # Each computer has its own fitted formula; "power_model" is from before devices were stored.
    return "power_model" if device_id is None else f"power_model:{device_id}"


def get_power_model(conn, device_id=None):
    for key in dict.fromkeys((_power_model_key(device_id), "power_model")):
        row = conn.execute("SELECT value FROM settings WHERE `key` = ?", (key,)).fetchone()
        if row:
            return PowerModel(**json.loads(row["value"]))
    return None


def set_power_model(conn, model, device_id=None):
    conn.execute("REPLACE INTO settings (`key`, value) VALUES (?, ?)",
                 (_power_model_key(device_id), json.dumps(model.to_dict())))
    conn.commit()


def latest_sample(conn, max_age_s=15):
    """The newest collector reading with its AI apps, or None if the collector isn't running."""
    s = conn.execute("SELECT * FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
    if not s or time.time() - s["ts"] > max_age_s:
        return None
    apps = conn.execute(
        f"SELECT COALESCE(model, app) AS name, {APP_COLUMNS} FROM ai_samples WHERE ts = ? ORDER BY watts DESC",
        (s["ts"],)
    ).fetchall()
    model = get_power_model(conn, s["device_id"]) or PowerModel()
    components = conn.execute(
        "SELECT component, watts, source FROM component_samples WHERE ts = ?", (s["ts"],)
    ).fetchall()
    measured = s["measured_watts"]
    return {
        # The sensor reading when there is one; otherwise the formula's estimate.
        "watts": round(measured if measured is not None else s["est_watts"], 1),
        "estimated": measured is None,
        "est_watts": round(s["est_watts"], 1),
        "measured_watts": measured,
        "cpu_percent": s["cpu_percent"],
        "gpu_percent": s["gpu_percent"],
        "ai_watts": round(sum(a["watts"] for a in apps), 2),
        "apps": [{**d, "activity": activity(d)} for d in map(dict, apps)],
        "components": {c["component"]: {"watts": c["watts"], "source": c["source"]} for c in components},
        "power_model": model.to_dict(),
        "device_id": s["device_id"],
        "source": "collector",
        "simulated": False,
    }


def daily_usage(conn, days=30, device_id=None):
    """Daily kWh per AI app or model.

    active_hours: time the app was doing work (CPU at or above ACTIVE_CPU_PCT of a core).
    """
    since = time.time() - days * 86400
    where, params = _device_filter(device_id)
    rows = conn.execute(
        f"""
        SELECT {conn.day()} AS date,
               COALESCE(model, app) AS model,
               kind,
               SUM(watts * interval_s) / 3600000.0 AS kwh,
               SUM(CASE WHEN cpu_percent >= ? THEN interval_s ELSE 0 END) / 3600.0 AS active_hours
        FROM ai_samples WHERE ts >= ?{where}
        GROUP BY 1, 2, 3 ORDER BY 1
        """,
        (ACTIVE_CPU_PCT, since, *params),
    ).fetchall()
    return [{"date": str(r["date"]), "model": r["model"], "kind": r["kind"],
             "kwh": round(r["kwh"], 6), "active_hours": round(r["active_hours"] or 0, 4),
             "source": "measured"} for r in rows]


def hourly_usage(conn, days=30, device_id=None):
    """{hour of day: kWh} of AI use in the last `days` days, summed over those days."""
    since = time.time() - days * 86400
    where, params = _device_filter(device_id)
    rows = conn.execute(
        f"SELECT {conn.hour()} AS hour, SUM(watts * interval_s) / 3600000.0 AS kwh "
        f"FROM ai_samples WHERE ts >= ?{where} GROUP BY 1",
        (since, *params),
    ).fetchall()
    return {int(r["hour"]): r["kwh"] or 0.0 for r in rows}


def measured_days(conn, days=60, device_id=None):
    """[{date, hours}]: days the collector ran, and for how long. Days missing here weren't
    measured, so they don't count as days without AI use."""
    since = time.time() - days * 86400
    where, params = _device_filter(device_id)
    rows = conn.execute(
        f"SELECT {conn.day()} AS date, SUM(interval_s) / 3600.0 AS hours FROM samples "
        f"WHERE ts >= ?{where} GROUP BY 1 ORDER BY 1",
        (since, *params),
    ).fetchall()
    return [{"date": str(r["date"]), "hours": round(r["hours"] or 0, 3)} for r in rows]


def idle_loaded(conn, days=7, device_id=None):
    """Local models that stayed loaded without generating: hours idle, energy used meanwhile, memory held."""
    since = time.time() - days * 86400
    where, params = _device_filter(device_id)
    rows = conn.execute(
        f"""
        SELECT model, SUM(interval_s) / 3600.0 AS hours, SUM(watts * interval_s) / 3600000.0 AS kwh,
               AVG(rss_mb) AS rss_mb
        FROM ai_samples
        WHERE ts >= ? AND kind = 'local' AND model IS NOT NULL AND cpu_percent < ?{where}
        GROUP BY model ORDER BY 2 DESC
        """,
        (since, ACTIVE_CPU_PCT, *params),
    ).fetchall()
    return [{"model": r["model"], "idle_hours": round(r["hours"], 3), "kwh": round(r["kwh"], 6),
             "rss_mb": round(r["rss_mb"] or 0, 1), "days": days} for r in rows]


def host_usage(conn, days=30, device_id=None, since=None):
    """kWh per AI app and the host it ran in (VS Code, Terminal, ...)."""
    since = time.time() - days * 86400 if since is None else since
    where, params = _device_filter(device_id)
    rows = conn.execute(
        f"""
        SELECT app, COALESCE(host, 'standalone') AS host, SUM(watts * interval_s) / 3600000.0 AS kwh
        FROM ai_samples WHERE ts >= ?{where} GROUP BY 1, 2 ORDER BY 3 DESC
        """,
        (since, *params),
    ).fetchall()
    return [{"app": r["app"], "host": r["host"], "kwh": round(r["kwh"], 6)} for r in rows]


def usage_records(conn, since, until=None, device_id=None, slot_s=None, limit=None):
    """AI readings added up per time slot, app, model, host and effort, newest slot first. A slot
    is `slot_s` seconds long, or a local calendar day when None.

    Each record: when its first reading began and its last one ended, how many readings it adds
    up, the seconds they cover, their energy in joules (watts × seconds) and the highest watts.
    """
    where, params = _device_filter(device_id)
    if until is not None:
        where, params = where + " AND ts <= ?", (*params, until)
    rows = conn.execute(
        f"""
        SELECT {conn.day() if slot_s is None else conn.slot(slot_s)} AS slot, app, model, kind, host, effort,
               MIN(ts - interval_s) AS start_ts, MAX(ts) AS end_ts, COUNT(*) AS readings,
               SUM(interval_s) AS seconds, SUM(watts * interval_s) AS joules, MAX(watts) AS peak_watts
        FROM ai_samples WHERE ts >= ?{where}
        GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY slot DESC, joules DESC{"" if limit is None else " LIMIT ?"}
        """,
        (since, *params, *(() if limit is None else (limit,))),
    ).fetchall()
    return [{**dict(r), "slot": str(r["slot"]) if slot_s is None else float(r["slot"]),
             "seconds": r["seconds"] or 0.0, "joules": r["joules"] or 0.0, "peak_watts": r["peak_watts"] or 0.0}
            for r in rows]


def app_part_usage(conn, days=30, device_id=None, since=None):
    """kWh per AI app or model, split into CPU, GPU and memory. Readings stored before the
    split was recorded count as "unsplit"."""
    since = time.time() - days * 86400 if since is None else since
    where, params = _device_filter(device_id)
    sums = ", ".join(f"SUM(COALESCE({p}_watts, 0) * interval_s) / 3600000.0 AS {p}_kwh" for p in ("cpu", "gpu", "memory"))
    rows = conn.execute(
        f"""
        SELECT COALESCE(model, app) AS model, {sums},
               SUM(CASE WHEN cpu_watts IS NULL THEN watts * interval_s ELSE 0 END) / 3600000.0 AS unsplit_kwh
        FROM ai_samples WHERE ts >= ?{where} GROUP BY 1
        """,
        (since, *params),
    ).fetchall()
    return [{"model": r["model"], **{k: round(r[k] or 0, 6) for k in ("cpu_kwh", "gpu_kwh", "memory_kwh", "unsplit_kwh")}}
            for r in rows]


def sample_count(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM samples").fetchone()["n"]


def daily_component_usage(conn, days=30, device_id=None):
    """Daily kWh per component (cpu, gpu, memory, disk, other) and how it was obtained."""
    since = time.time() - days * 86400
    where, params = _device_filter(device_id)
    rows = conn.execute(
        f"""
        SELECT {conn.day()} AS date, component,
               SUM(watts * interval_s) / 3600000.0 AS kwh,
               SUM(CASE WHEN source IN ('estimated', ?) THEN 0 ELSE interval_s END)
                   / SUM(interval_s) AS measured_share
        FROM component_samples WHERE ts >= ?{where}
        GROUP BY 1, 2 ORDER BY 1, 2
        """,
        (DERIVED, since, *params),
    ).fetchall()
    return [{"date": str(r["date"]), "component": r["component"], "kwh": round(r["kwh"], 6),
             "measured_share": round(r["measured_share"], 3)} for r in rows]


def readings(conn, since=None, until=None, device_id=None, limit=1000):
    """Stored readings, newest first, each with its per-component watts and AI apps."""
    where, params = ["1 = 1"], []
    for clause, value in (("ts >= ?", since), ("ts <= ?", until), ("device_id = ?", device_id)):
        if value is not None:
            where.append(clause)
            params.append(value)
    rows = [dict(r) for r in conn.execute(
        f"SELECT ts, device_id, interval_s, cpu_percent, gpu_percent, est_watts, measured_watts FROM samples "
        f"WHERE {' AND '.join(where)} ORDER BY ts DESC LIMIT ?", (*params, limit)
    ).fetchall()]
    if not rows:
        return rows
    lo, hi = rows[-1]["ts"], rows[0]["ts"]
    parts, apps = {}, {}
    for r in conn.execute("SELECT ts, device_id, component, watts, source FROM component_samples "
                          "WHERE ts BETWEEN ? AND ?", (lo, hi)):
        parts.setdefault((r["ts"], r["device_id"]), {})[r["component"]] = {"watts": r["watts"], "source": r["source"]}
    for r in conn.execute(f"SELECT ts, device_id, {APP_COLUMNS} FROM ai_samples WHERE ts BETWEEN ? AND ?", (lo, hi)):
        r = dict(r)
        apps.setdefault((r.pop("ts"), r.pop("device_id")), []).append(r)
    for r in rows:
        key = (r["ts"], r["device_id"])
        r["components"], r["apps"] = parts.get(key, {}), apps.get(key, [])
    return rows


# --- Wall-meter checks ------------------------------------------------------
# A plug-in power meter or smart plug reads the whole machine at the wall: the ground truth
# for our whole-machine watts. "watts" checks compare one meter reading with our average over
# the last few seconds; "kwh" checks compare the meter's kWh counter over a window with ours.

def machine_energy(conn, since, until, device_id=None):
    """Our whole-machine energy between two times: the sensor reading where there is one,
    else the formula's estimate. coverage: share of the time the device reader was running."""
    where, params = _device_filter(device_id)
    r = conn.execute(
        f"""
        SELECT SUM(COALESCE(measured_watts, est_watts) * interval_s) AS joules, SUM(interval_s) AS seconds,
               SUM(CASE WHEN measured_watts IS NULL THEN 0 ELSE interval_s END) AS measured_s
        FROM samples WHERE ts > ? AND ts <= ?{where}
        """,
        (since, until, *params),
    ).fetchone()
    seconds = r["seconds"] or 0.0
    span = max(until - since, 1e-9)
    return {"kwh": (r["joules"] or 0.0) / 3_600_000, "seconds": seconds,
            "avg_watts": (r["joules"] or 0.0) / seconds if seconds else None,
            "coverage": min(seconds / span, 1.0), "measured_share": (r["measured_s"] or 0.0) / seconds if seconds else 0.0}


def add_meter_check(conn, kind, started_at, ended_at=None, meter_start=None, meter_end=None,
                    app_value=None, coverage=None, device_id=None):
    cur = conn.execute(
        "INSERT INTO meter_checks (device_id, kind, started_at, ended_at, meter_start, meter_end, app_value, coverage) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (device_id, kind, started_at, ended_at, meter_start, meter_end, app_value, coverage))
    conn.commit()
    return cur.lastrowid


def finish_meter_check(conn, check_id, ended_at, meter_end, app_value, coverage):
    conn.execute("UPDATE meter_checks SET ended_at = ?, meter_end = ?, app_value = ?, coverage = ? WHERE id = ?",
                 (ended_at, meter_end, app_value, coverage, check_id))
    conn.commit()


def delete_meter_check(conn, check_id):
    conn.execute("DELETE FROM meter_checks WHERE id = ?", (check_id,))
    conn.commit()


def meter_checks(conn, device_id=None):
    """Every check, newest first. An open kWh check has no ended_at yet."""
    where, params = _device_filter(device_id)
    return [dict(r) for r in conn.execute(
        f"SELECT * FROM meter_checks WHERE 1 = 1{where} ORDER BY started_at DESC", params).fetchall()]
