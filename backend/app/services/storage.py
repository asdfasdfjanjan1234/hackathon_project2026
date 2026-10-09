"""SQLite storage for collector readings."""

import json
import os
import sqlite3
import time

from .attribution import PowerModel
from .measurement import DERIVED

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    ts REAL, interval_s REAL, cpu_percent REAL, gpu_percent REAL,
    est_watts REAL, measured_watts REAL
);
CREATE TABLE IF NOT EXISTS ai_samples (
    ts REAL, interval_s REAL, app TEXT, model TEXT, kind TEXT,
    cpu_percent REAL, rss_mb REAL, watts REAL, host TEXT
);
CREATE TABLE IF NOT EXISTS power_windows (
    ts REAL, avg_watts REAL, avg_cpu REAL, avg_gpu REAL, n_samples INTEGER
);
CREATE TABLE IF NOT EXISTS component_samples (
    ts REAL, interval_s REAL, component TEXT, watts REAL, source TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
CREATE INDEX IF NOT EXISTS idx_ai_samples_ts ON ai_samples(ts);
CREATE INDEX IF NOT EXISTS idx_component_samples_ts ON component_samples(ts);
"""


def connect(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # The device reader writes from its own thread while requests read, so wait on locks.
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Databases from before the host column was added.
    if "host" not in {r["name"] for r in conn.execute("PRAGMA table_info(ai_samples)")}:
        conn.execute("ALTER TABLE ai_samples ADD COLUMN host TEXT")
    return conn


def save_sample(conn, ts, interval_s, cpu, gpu, est_watts, measured_watts, apps, components=None):
    conn.execute("INSERT INTO samples VALUES (?, ?, ?, ?, ?, ?)",
                 (ts, interval_s, cpu, gpu, est_watts, measured_watts))
    conn.executemany(
        "INSERT INTO ai_samples (ts, interval_s, app, model, kind, cpu_percent, rss_mb, watts, host) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(ts, interval_s, a["app"], a["model"], a["kind"], a["cpu_percent"], a["rss_mb"], a["watts"], a.get("host"))
         for a in apps],
    )
    conn.executemany(
        "INSERT INTO component_samples VALUES (?, ?, ?, ?, ?)",
        [(ts, interval_s, name, c["watts"], c["source"]) for name, c in (components or {}).items()],
    )
    conn.commit()


def save_window(conn, ts, avg_watts, avg_cpu, avg_gpu, n_samples):
    conn.execute("INSERT INTO power_windows VALUES (?, ?, ?, ?, ?)", (ts, avg_watts, avg_cpu, avg_gpu, n_samples))
    conn.commit()


def recent_windows(conn, limit=500):
    rows = conn.execute(
        "SELECT avg_watts, avg_cpu, avg_gpu FROM power_windows ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    return [tuple(r) for r in rows]


def get_power_model(conn):
    row = conn.execute("SELECT value FROM settings WHERE key = 'power_model'").fetchone()
    return PowerModel(**json.loads(row["value"])) if row else None


def set_power_model(conn, model):
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('power_model', ?)", (json.dumps(model.to_dict()),))
    conn.commit()


def latest_sample(conn, max_age_s=15):
    """The newest collector reading with its AI apps, or None if the collector isn't running."""
    s = conn.execute("SELECT * FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
    if not s or time.time() - s["ts"] > max_age_s:
        return None
    apps = conn.execute(
        "SELECT COALESCE(model, app) AS name, app, kind, host, cpu_percent, rss_mb, watts "
        "FROM ai_samples WHERE ts = ? ORDER BY watts DESC", (s["ts"],)
    ).fetchall()
    model = get_power_model(conn) or PowerModel()
    components = conn.execute(
        "SELECT component, watts, source FROM component_samples WHERE ts = ?", (s["ts"],)
    ).fetchall()
    return {
        "watts": round(s["est_watts"], 1),
        "measured_watts": s["measured_watts"],
        "cpu_percent": s["cpu_percent"],
        "gpu_percent": s["gpu_percent"],
        "ai_watts": round(sum(a["watts"] for a in apps), 2),
        "apps": [dict(a) for a in apps],
        "components": {c["component"]: {"watts": c["watts"], "source": c["source"]} for c in components},
        "power_model": model.to_dict(),
        "source": "collector",
        "simulated": False,
    }


def daily_usage(conn, days=30):
    """Daily kWh per AI app or model, in the same shape as the sample data."""
    since = time.time() - days * 86400
    rows = conn.execute(
        """
        SELECT date(ts, 'unixepoch', 'localtime') AS date,
               COALESCE(model, app) AS model,
               kind,
               SUM(watts * interval_s) / 3600000.0 AS kwh
        FROM ai_samples WHERE ts >= ?
        GROUP BY 1, 2, 3 ORDER BY 1
        """,
        (since,),
    ).fetchall()
    return [{"date": r["date"], "model": r["model"], "kind": r["kind"],
             "kwh": round(r["kwh"], 6), "source": "measured"} for r in rows]


def host_usage(conn, days=30):
    """kWh per AI app and the host it ran in (VS Code, Terminal, ...)."""
    since = time.time() - days * 86400
    rows = conn.execute(
        """
        SELECT app, COALESCE(host, 'standalone') AS host, SUM(watts * interval_s) / 3600000.0 AS kwh
        FROM ai_samples WHERE ts >= ? GROUP BY 1, 2 ORDER BY 3 DESC
        """,
        (since,),
    ).fetchall()
    return [{"app": r["app"], "host": r["host"], "kwh": round(r["kwh"], 6)} for r in rows]


def sample_count(conn):
    return conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]


def daily_component_usage(conn, days=30):
    """Daily kWh per component (cpu, gpu, memory, disk, other) and how it was obtained."""
    since = time.time() - days * 86400
    rows = conn.execute(
        """
        SELECT date(ts, 'unixepoch', 'localtime') AS date, component,
               SUM(watts * interval_s) / 3600000.0 AS kwh,
               SUM(CASE WHEN source IN ('estimated', ?) THEN 0 ELSE interval_s END)
                   / SUM(interval_s) AS measured_share
        FROM component_samples WHERE ts >= ?
        GROUP BY 1, 2 ORDER BY 1, 2
        """,
        (DERIVED, since),
    ).fetchall()
    return [{"date": r["date"], "component": r["component"], "kwh": round(r["kwh"], 6),
             "measured_share": round(r["measured_share"], 3)} for r in rows]
