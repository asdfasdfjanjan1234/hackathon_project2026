"""Access to daily per-model energy usage.

For now this returns sample data. Replace with a database (e.g. SQLite)
that the measurement collector writes to.
"""

from collections import defaultdict

from flask import current_app

from .models_catalog import MODELS
from .sample_data import generate_daily_usage


def get_daily_usage():
    if current_app.config["USE_SAMPLE_DATA"]:
        return generate_daily_usage()
    raise NotImplementedError("Real usage storage is not built yet. Set USE_SAMPLE_DATA=true.")


def summarize_by_model(daily, rate):
    totals = defaultdict(float)
    for row in daily:
        totals[row["model"]] += row["kwh"]
    return sorted(
        (
            {
                "model": model,
                "kwh": round(kwh, 2),
                "cost": round(kwh * rate, 2),
                "kind": MODELS[model]["kind"],
                "source": MODELS[model]["source"],
            }
            for model, kwh in totals.items()
        ),
        key=lambda m: m["kwh"],
        reverse=True,
    )
