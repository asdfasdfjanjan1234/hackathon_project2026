"""Generates realistic daily usage so the dashboard works before real measurement is ready."""

import random
from datetime import date, timedelta

from .models_catalog import MODELS

# Average hours per day each local model runs, and tokens per day for cloud models.
_DAILY_HOURS = {"llama3:70b": 6.5, "llama3:8b": 2.0, "sdxl-turbo": 1.5}
_DAILY_TOKENS = {"claude (cloud)": 400_000}


def generate_daily_usage(days=30, seed=42):
    rng = random.Random(seed)
    today = date.today()
    rows = []
    for i in range(days, 0, -1):
        day = today - timedelta(days=i)
        growth = 1 + (days - i) * 0.01  # usage creeps up over time
        weekend = 0.6 if day.weekday() >= 5 else 1.0
        for model, info in MODELS.items():
            if info["kind"] == "local":
                hours = _DAILY_HOURS[model] * growth * weekend * rng.uniform(0.7, 1.3)
                kwh = info["avg_watts"] * hours / 1000
            else:
                tokens = _DAILY_TOKENS[model] * growth * weekend * rng.uniform(0.7, 1.3)
                kwh = tokens / 1000 * info["wh_per_1k_tokens"] / 1000
            rows.append({
                "date": day.isoformat(),
                "model": model,
                "kwh": round(kwh, 4),
                "kind": info["kind"],
                "source": info["source"],
            })
    return rows
