"""Access to daily per-model energy usage: sample data, or what collect.py recorded."""

from collections import defaultdict
from contextlib import closing

from flask import current_app

from . import storage
from .sample_data import generate_daily_usage


def get_daily_usage():
    cfg = current_app.config
    if cfg["USE_SAMPLE_DATA"]:
        return generate_daily_usage()
    with closing(storage.connect(cfg["DB_PATH"])) as conn:
        return storage.daily_usage(conn)


def summarize_by_model(daily, rate):
    totals = defaultdict(float)
    meta = {}
    for row in daily:
        totals[row["model"]] += row["kwh"]
        meta[row["model"]] = {"kind": row["kind"], "source": row["source"]}
    return sorted(
        ({"model": model, "kwh": round(kwh, 4), "cost": round(kwh * rate, 2), **meta[model]}
         for model, kwh in totals.items()),
        key=lambda m: m["kwh"],
        reverse=True,
    )
