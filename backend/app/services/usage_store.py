"""Access to daily per-model energy usage: sample data, or what the device reader recorded."""

import platform
from collections import defaultdict
from contextlib import closing
from functools import lru_cache

from flask import current_app

from . import storage
from .local_models import installed_local_models
from .model_usage import model_usage
from .sample_data import generate_daily_usage, sample_signals
from .system_info import machine_id


def data_source():
    """"device" or "sample". Starts from USE_SAMPLE_DATA; "Start reading my device" switches it."""
    cfg = current_app.config
    return cfg.get("DATA_SOURCE") or ("sample" if cfg["USE_SAMPLE_DATA"] else "device")


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


def get_daily_usage():
    if data_source() == "sample":
        return generate_daily_usage()
    with connect() as conn:
        return storage.daily_usage(conn, device_id=this_device_id(conn))


def get_signals():
    """What recommendations and the forecast need besides daily kWh: which days were measured,
    loaded-but-idle models, installed local models, and the cloud-model switch hint."""
    if data_source() == "sample":
        return sample_signals()
    with connect() as conn:
        device = this_device_id(conn)
        measured = storage.measured_days(conn, device_id=device)
        idle = storage.idle_loaded(conn, device_id=device)
    return {"measured_days": measured, "idle_loaded": idle, "installed": installed_local_models(),
            "cloud": model_usage()["switch_hint"]}


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
