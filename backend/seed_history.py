"""Adds made-up AI usage history before this device's first real reading, so the ARIMA forecast
has days and weeks to learn from while the real readings are still only hours long.

    python seed_history.py                 14 days before the first real reading
    python seed_history.py --days 21 --scale 5
    python seed_history.py --dry-run       print what it would add, write nothing
    python seed_history.py --remove        delete the made-up history again

The made-up days follow a routine, so the model has something to find: the computer is on from
morning to past midnight, coding agents (Claude Code, Copilot, Kiro) work office hours on
weekdays, and a local model (Ollama) runs in the evenings and on weekend afternoons. Busy and
quiet stretches carry over from one 15 minutes to the next, as real use does.

Rows are written to the same tables the device reader fills (samples, ai_samples,
power_windows), one reading a minute, all before the first real reading. The time range is
kept in settings (synthetic_history:<device id>), which is how --remove finds it again; real
readings are never touched. The dashboard's history, usage and forecast all count these rows
until they are removed.
"""

import argparse
import json
import math
import random
import sys
import time
from contextlib import closing
from datetime import datetime

from app.config import Config
from app.services import storage
from app.services.usage_store import this_machine_id

STEP_S = 60      # one reading a minute; the device reader takes one every 2 s
BLOCK_S = 900    # busy or quiet is decided per 15 minutes, the model's step

# app, model, kind, host, effort: as the device reader records them on this machine
CLAUDE = ("Claude Code", "Claude Code · claude-opus-5-5", "client", "VS Code", "xhigh")
CLAUDE_TOOLS = ("Claude Code", "Claude Code · tool runs", "client", "VS Code", None)
COPILOT = ("GitHub Copilot", "GitHub Copilot · gpt-4o-mini-2024-07-18", "client", "VS Code", None)
KIRO = ("Kiro", "Kiro · qwen3-coder-next", "client", None, None)
DEVIN = ("Devin Desktop", None, "client", None, None)
OLLAMA = ("Ollama", "Ollama · qwen3.5:4b-q4_K_M", "local", "VS Code", None)


def _work(hour, weekend):
    """How likely coding agents are busy in this hour (0-1)."""
    if weekend:
        return 0.25 if 14 <= hour < 18 else 0.05
    if 9 <= hour < 12 or 13 <= hour < 18:
        return 0.85
    if 20 <= hour < 23:
        return 0.35
    return 0.05


def _evening(hour, weekend):
    """How likely the local model is generating in this hour (0-1)."""
    if weekend:
        return 0.55 if 13 <= hour < 17 or 20 <= hour < 23 else 0.05
    return 0.6 if 19 <= hour < 22 else 0.03


# Each app: its readings while busy and while open but quiet, in watts, and how busy it is by hour.
APPS = [
    # (row, busy W, quiet W, cpu % busy, chance of being busy by hour, GPU share of its watts)
    (CLAUDE, 0.55, 0.04, 22.0, _work, 0.0),
    (CLAUDE_TOOLS, 0.45, 0.0, 30.0, lambda h, w: _work(h, w) * 0.6, 0.0),
    (COPILOT, 0.03, 0.002, 2.0, _work, 0.0),
    (KIRO, 0.30, 0.02, 12.0, lambda h, w: _work(h, w) * (1.0 if 13 <= h < 18 else 0.3), 0.0),
    (DEVIN, 0.04, 0.03, 1.5, _work, 0.0),
    (OLLAMA, 4.5, 0.03, 45.0, _evening, 0.86),
]


def _key(device_id):
    return f"synthetic_history:{device_id}"


def _on_hours(weekend, rng):
    """(start, end) the computer is on that day, in hours after midnight (end may pass 24)."""
    start = (9.5 if weekend else 7.5) + rng.uniform(-0.5, 0.75)
    end = (25.0 if weekend else 24.5) + rng.uniform(-1.0, 0.5)
    return start, end


def generate(device_id, start_ts, end_ts, scale, seed):
    """(samples, ai_samples, power_windows) rows for [start_ts, end_ts)."""
    rng = random.Random(seed)
    samples, apps, windows = [], [], []
    mood = {row: 0.0 for row, *_ in APPS}  # carries busy/quiet over from one 15 minutes to the next
    busy = {}
    day0 = datetime.fromtimestamp(start_ts).replace(hour=0, minute=0, second=0, microsecond=0)
    on = {}
    ts = start_ts - start_ts % STEP_S + STEP_S
    while ts < end_ts:
        now = datetime.fromtimestamp(ts)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Hours since the midnight of the day this stretch of use started (a night past 24:00 counts
        # to the day before).
        days_in = (midnight - day0).days
        for d in (days_in - 1, days_in):
            if d not in on:
                on[d] = _on_hours((day0.weekday() + d) % 7 >= 5, rng)
        hour_of = (ts - midnight.timestamp()) / 3600
        is_on = (on[days_in][0] <= hour_of < on[days_in][1]) or (hour_of + 24 < on[days_in - 1][1])
        if not is_on:
            ts += STEP_S
            continue
        weekend = now.weekday() >= 5
        if ts % BLOCK_S < STEP_S:  # a new 15 minutes: decide who's busy in it
            for row, _, _, _, chance, _ in APPS:
                mood[row] = 0.8 * mood[row] + rng.gauss(0, 0.6)
                p = chance(now.hour, weekend)
                busy[row] = rng.random() < 1 / (1 + math.exp(-(math.log(p / (1 - p)) + 1.5 * mood[row])))
        total_ai = 0.0
        for row, busy_w, quiet_w, busy_cpu, _, gpu_share in APPS:
            app, model, kind, host, effort = row
            on_now = busy.get(row, False)
            if not on_now and quiet_w == 0:
                continue  # tool runs only exist while Claude Code is working
            watts = (busy_w * rng.lognormvariate(0, 0.35) if on_now else quiet_w * rng.uniform(0.6, 1.4)) * scale
            cpu = busy_cpu * rng.uniform(0.5, 1.5) if on_now else rng.uniform(0.0, 0.8)
            gpu_w = watts * gpu_share
            mem_w = watts * (0.12 if kind == "local" else 0.15)
            local = kind == "local"
            apps.append((ts, STEP_S, device_id, app, model, kind, host, round(cpu, 2),
                         3400.0 if local else 350.0, round(watts, 5), effort,
                         round(watts - gpu_w - mem_w, 5), round(gpu_w, 5), round(mem_w, 5),
                         gpu_share if local else None, 3400.0 if local else None, 3400.0 if local else None))
            total_ai += watts
        cpu = min(100.0, rng.uniform(4, 12) + total_ai * 4)
        gpu = min(100.0, rng.uniform(0, 5) + (60.0 if busy.get(OLLAMA) else 0.0))
        est = round(5.0 + cpu * 0.12 + gpu * 0.05 + total_ai, 3)
        samples.append((ts, STEP_S, round(cpu, 2), round(gpu, 2), est, None, device_id))
        windows.append((ts, est, round(cpu, 2), round(gpu, 2), 30, device_id))
        ts += STEP_S
    return samples, apps, windows


def _first_real(conn, device_id):
    row = conn.execute("SELECT MIN(ts) AS ts FROM samples WHERE device_id = ?", (device_id,)).fetchone()
    return row["ts"] if row and row["ts"] is not None else None


def remove(conn, device_id):
    row = conn.execute("SELECT value FROM settings WHERE `key` = ?", (_key(device_id),)).fetchone()
    if not row:
        print(f"No made-up history recorded for device {device_id}.")
        return
    span = json.loads(row["value"])
    for table in storage.READING_TABLES:
        n = conn.execute(f"DELETE FROM {table} WHERE device_id = ? AND ts >= ? AND ts < ?",
                         (device_id, span["start"], span["end"])).rowcount
        print(f"  {table}: {n} rows removed")
    conn.execute("DELETE FROM settings WHERE `key` = ?", (_key(device_id),))
    conn.commit()
    print(f"Removed the made-up history from {datetime.fromtimestamp(span['start']):%Y-%m-%d %H:%M} "
          f"to {datetime.fromtimestamp(span['end']):%Y-%m-%d %H:%M}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14, help="days of history to add (default 14)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="multiply every app's watts (default 1: about what this machine draws)")
    ap.add_argument("--seed", type=int, default=7, help="random seed, for the same history every time")
    ap.add_argument("--device-id", type=int, help="device to add it to (default: this computer)")
    ap.add_argument("--dry-run", action="store_true", help="print what would be added, write nothing")
    ap.add_argument("--remove", action="store_true", help="delete the made-up history again")
    args = ap.parse_args()

    print(f"Database: {storage.describe(Config.DATABASE)}")
    with closing(storage.connect(Config.DATABASE)) as conn:
        device_id = args.device_id or storage.device_id_for(conn, this_machine_id())
        if device_id is None:
            sys.exit("This computer has no readings yet. Start the device reader once, then run this again.")
        if args.remove:
            return remove(conn, device_id)
        if conn.execute("SELECT 1 FROM settings WHERE `key` = ?", (_key(device_id),)).fetchone():
            sys.exit(f"Device {device_id} already has made-up history. Run with --remove first to replace it.")

        end = _first_real(conn, device_id) or time.time()
        start = end - args.days * 86400
        samples, apps, windows = generate(device_id, start, end, args.scale, args.seed)
        kwh = sum(r[9] * r[1] for r in apps) / 3.6e6
        hours = len(samples) * STEP_S / 3600
        print(f"Device {device_id}: {datetime.fromtimestamp(start):%Y-%m-%d %H:%M} to "
              f"{datetime.fromtimestamp(end):%Y-%m-%d %H:%M} (before its first real reading)")
        print(f"  {len(samples)} readings ({hours:.0f} hours on), {len(apps)} app rows, "
              f"{kwh:.4f} kWh of AI ({kwh / args.days * 1000:.1f} Wh a day)")
        if args.dry_run:
            print("Dry run: nothing written.")
            return

        conn.executemany("INSERT INTO samples (ts, interval_s, cpu_percent, gpu_percent, est_watts, "
                         "measured_watts, device_id) VALUES (?, ?, ?, ?, ?, ?, ?)", samples)
        conn.executemany(f"INSERT INTO ai_samples (ts, interval_s, device_id, {storage.APP_COLUMNS}) "
                         f"VALUES ({', '.join(['?'] * 17)})", apps)
        conn.executemany("INSERT INTO power_windows (ts, avg_watts, avg_cpu, avg_gpu, n_samples, device_id) "
                         "VALUES (?, ?, ?, ?, ?, ?)", windows)
        conn.execute("REPLACE INTO settings (`key`, value) VALUES (?, ?)",
                     (_key(device_id), json.dumps({"start": start, "end": end, "days": args.days,
                                                   "scale": args.scale, "seed": args.seed, "created": time.time()})))
        conn.commit()
        print("Written. Remove it again with: python seed_history.py --remove")


if __name__ == "__main__":
    main()
