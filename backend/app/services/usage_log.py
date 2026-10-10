"""The usage log: what each AI app drew, when, in which IDE, with which model and effort.

The device reader stores one row per AI app every couple of seconds (`ai_samples`): the
timestamp, the seconds since the previous reading, the app, the IDE or terminal it ran in, the
model it was using, the reasoning effort it asked for, and the watts attributed to it. Energy
is those watts added up over time:

    E (Wh) = Σ Pᵢ · Δtᵢ / 3600        Pᵢ = watts of reading i, Δtᵢ = seconds it covers

A total by date, IDE, app, model or effort is the same sum over the readings in that group.
Every reading is in exactly one group, so the groups of any one breakdown add up to the total.
"""

from collections import defaultdict
from datetime import datetime

# Breakdowns of the total: id -> the field of a record it groups by.
DIMENSIONS = {"date": "date", "ide": "ide", "app": "app", "model": "model_name", "effort": "effort"}
# Lengths of a record's time slot the dashboard offers, in seconds.
SLOTS = (60, 900, 3600)
SEP = " · "


def describe(row):
    """A stored record with the fields the log shows: the IDE it ran in (a standalone app is its
    own), the model's name without the app in front, and the times as local ISO timestamps."""
    app, model = row["app"], row["model"]
    name = model[len(app) + len(SEP):] if model and model.startswith(app + SEP) else model
    seconds, joules = row["seconds"], row["joules"]
    return {
        "start_ts": row["start_ts"], "end_ts": row["end_ts"],
        "start": _iso(row["start_ts"]), "end": _iso(row["end_ts"]),
        "date": row["slot"] if isinstance(row["slot"], str) else _iso(row["slot"])[:10],
        "ide": row["host"] or app, "app": app, "model_name": name, "effort": row["effort"], "kind": row["kind"],
        "readings": row["readings"], "seconds": round(seconds, 3),
        "wh": round(joules / 3600, 6),
        "avg_watts": round(joules / seconds, 4) if seconds else None,
        "peak_watts": round(row["peak_watts"], 4),
    }


def _iso(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def _sum(records, rate):
    """Energy, time and watts of a set of records: E = Σ P·Δt, average P = E / Σ Δt."""
    seconds = sum(r["seconds"] for r in records)
    wh = sum(r["wh"] for r in records)
    return {
        "wh": round(wh, 6), "kwh": round(wh / 1000, 9), "cost": round(wh / 1000 * rate, 4),
        "seconds": round(seconds, 3),
        "avg_watts": round(wh * 3600 / seconds, 4) if seconds else None,
        "peak_watts": max((r["peak_watts"] for r in records), default=0.0),
        "readings": sum(r["readings"] for r in records),
        "start_ts": min((r["start_ts"] for r in records), default=None),
        "end_ts": max((r["end_ts"] for r in records), default=None),
    }


def totals(records, dimension, rate):
    """The records added up by one dimension, biggest first (dates: newest first). `key` is None
    for records with nothing logged, e.g. an app that doesn't record its effort."""
    groups = defaultdict(list)
    for r in records:
        groups[r[DIMENSIONS[dimension]]].append(r)
    all_wh = sum(r["wh"] for r in records)
    rows = [{"key": key, **_sum(rs, rate), "share": round(sum(r["wh"] for r in rs) / all_wh, 4) if all_wh else 0.0}
            for key, rs in groups.items()]
    if dimension == "date":
        return sorted(rows, key=lambda r: r["key"], reverse=True)
    return sorted(rows, key=lambda r: r["wh"], reverse=True)


def usage_log(daily, slots, rate):
    """`daily` and `slots` are storage.usage_records per day and per time slot."""
    days = [describe(r) for r in daily]
    return {
        "total": _sum(days, rate),
        "totals": {d: totals(days, d, rate) for d in DIMENSIONS},
        "records": [describe(r) for r in slots],
    }


CSV_COLUMNS = ("start", "end", "ide", "app", "model_name", "effort", "kind", "readings", "seconds",
               "avg_watts", "peak_watts", "wh")
