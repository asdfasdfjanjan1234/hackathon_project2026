"""Access to daily per-model energy usage recorded by the device reader."""

import platform
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta
from functools import lru_cache

from flask import current_app

from . import storage
from .clean_hours import clean_hours
from .local_models import installed_local_models
from .model_usage import model_usage
from .system_info import machine_id


@lru_cache(maxsize=1)
def this_machine_id():
    os_name = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(platform.system(), "other")
    return machine_id(os_name)


def this_device_id(conn):
    """This computer's id in the database, so a database shared by several computers (MySQL)
    shows only this one's readings. None before it has taken any: then nothing is filtered."""
    return storage.device_id_for(conn, this_machine_id())


def connect():
    return closing(storage.connect(current_app.config["DATABASE"]))


def get_daily_usage(days=30):
    with connect() as conn:
        return storage.daily_usage(conn, days=days, device_id=this_device_id(conn))


# The dashboard's time windows: id -> (short label, label).
WINDOWS = {"7d": ("7D", "Last 7 days"), "30d": ("30D", "Last 30 days"), "month": ("MTD", "Month to date")}


def usage_window(window_id, end=None):
    """The 7D, 30D or MTD window: N calendar days through `end` (default today), or the 1st of
    the month through `end`."""
    if window_id not in WINDOWS:
        window_id = "30d"
    end = end or date.today()
    if window_id == "month":
        start = end.replace(day=1)
    else:
        start = end - timedelta(days=(7 if window_id == "7d" else 30) - 1)
    short, label = WINDOWS[window_id]
    return {"id": window_id, "short": short, "label": label, "start": start.isoformat(),
            "end": end.isoformat(), "days": (end - start).days + 1,
            "since_ts": datetime.combine(start, datetime.min.time()).timestamp()}


def get_hourly_usage(days=30):
    """{hour of day: average AI kWh a day in that hour}, over the days the device reader ran."""
    with connect() as conn:
        device = this_device_id(conn)
        totals = storage.hourly_usage(conn, days=days, device_id=device)
        measured = len(storage.measured_days(conn, days=days, device_id=device))
    return {h: kwh / measured for h, kwh in totals.items()} if measured else {}


def get_clean_hours(use_by_hour=None):
    return clean_hours(get_hourly_usage() if use_by_hour is None else use_by_hour, current_app.config)


def get_signals():
    """What recommendations and the forecast need besides daily kWh: which days were measured,
    loaded-but-idle models, installed local models, the cloud-model switch hint, AI use by hour
    of day, and the grid's cleanest hours."""
    with connect() as conn:
        device = this_device_id(conn)
        measured = storage.measured_days(conn, device_id=device)
        idle = storage.idle_loaded(conn, device_id=device)
    hourly = get_hourly_usage()
    return {"measured_days": measured, "idle_loaded": idle, "installed": installed_local_models(),
            "cloud": model_usage()["switch_hint"], "hourly_use": hourly, "clean_hours": get_clean_hours(hourly)}


def summarize_by_model(daily, rate):
    totals = defaultdict(float)
    hours = defaultdict(float)
    meta = {}
    for row in daily:
        totals[row["model"]] += row["kwh"]
        hours[row["model"]] += row.get("active_hours") or 0.0
        meta[row["model"]] = {"kind": row["kind"], "source": row["source"]}
    return sorted(
        ({"model": model, "kwh": round(kwh, 6), "cost": round(kwh * rate, 4),
          "active_hours": round(hours[model], 3),
          # Average power while the model was doing work: a measure of how heavy it is to run.
          "active_watts": round(kwh * 1000 / hours[model], 2) if hours[model] > 0 else None,
          **meta[model]}
         for model, kwh in totals.items()),
        key=lambda m: m["kwh"],
        reverse=True,
    )


def equivalents(kwh):
    """kWh in relatable terms: CO₂ from the grid, aircon hours, trees offset, smartphone charges, and EV km."""
    cfg = current_app.config
    co2 = kwh * cfg["GRID_CO2_KG_PER_KWH"]
    return {
        "kwh": round(kwh, 6),
        "co2_kg": round(co2, 4),
        "aircon_hours": round(kwh * 1000 / cfg["AIRCON_WATTS"], 3),
        "trees_offset": round(co2 / 1.81, 1),
        "smartphone_charges": int(kwh * 1000 / 12),
        "ev_km": round(kwh / 0.18, 1),
    }


def equivalence_factors():
    cfg = current_app.config
    return {"co2_kg_per_kwh": cfg["GRID_CO2_KG_PER_KWH"], "co2_source": cfg["GRID_CO2_SOURCE"],
            "aircon_watts": cfg["AIRCON_WATTS"]}
