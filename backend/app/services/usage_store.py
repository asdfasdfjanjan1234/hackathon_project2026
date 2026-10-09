"""Access to daily per-model energy usage: sample data, or what the device reader recorded."""

from collections import defaultdict
from contextlib import closing

from flask import current_app

from . import storage
from .sample_data import generate_daily_usage


def data_source():
    """"device" or "sample". Starts from USE_SAMPLE_DATA; "Start reading my device" switches it."""
    cfg = current_app.config
    return cfg.get("DATA_SOURCE") or ("sample" if cfg["USE_SAMPLE_DATA"] else "device")


def get_daily_usage():
    if data_source() == "sample":
        return generate_daily_usage()
    with closing(storage.connect(current_app.config["DATABASE"])) as conn:
        return storage.daily_usage(conn)


def summarize_by_model(daily, rate):
    totals = defaultdict(float)
    meta = {}
    for row in daily:
        totals[row["model"]] += row["kwh"]
        meta[row["model"]] = {"kind": row["kind"], "source": row["source"]}
    return sorted(
        ({"model": model, "kwh": round(kwh, 6), "cost": round(kwh * rate, 4), **meta[model]}
         for model, kwh in totals.items()),
        key=lambda m: m["kwh"],
        reverse=True,
    )
