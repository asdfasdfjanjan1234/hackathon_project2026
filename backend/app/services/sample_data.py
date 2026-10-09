"""Generates realistic daily usage so the dashboard works before real measurement is ready."""

import random
from datetime import date, timedelta

from .models_catalog import LOCAL_MODELS

# Average hours per day each local model runs on John's gaming PC.
_DAILY_HOURS = {"llama3:70b": 6.5, "llama3:8b": 2.0, "sdxl-turbo": 1.5}


def generate_daily_usage(days=30, seed=42):
    rng = random.Random(seed)
    today = date.today()
    rows = []
    for i in range(days, 0, -1):
        day = today - timedelta(days=i)
        growth = 1 + (days - i) * 0.01  # usage creeps up over time
        weekend = 0.6 if day.weekday() >= 5 else 1.0
        for model, info in LOCAL_MODELS.items():
            hours = _DAILY_HOURS[model] * growth * weekend * rng.uniform(0.7, 1.3)
            rows.append({
                "date": day.isoformat(),
                "model": model,
                "kwh": round(info["avg_watts"] * hours / 1000, 4),
                "kind": "local",
                "source": "measured",
            })
    return rows
