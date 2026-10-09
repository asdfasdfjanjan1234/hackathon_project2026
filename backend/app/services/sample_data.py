"""Generates realistic daily usage so the dashboard works before real measurement is ready."""

import random
from datetime import date, timedelta

from .models_catalog import LOCAL_MODELS

# Average hours per day each local model runs on John's gaming PC.
_DAILY_HOURS = {"llama3:70b": 6.5, "llama3:8b": 2.0, "sdxl-turbo": 1.5}
# Hours per day llama3:70b stays loaded in GPU memory after John's last prompt.
_IDLE_LOADED_HOURS = 6.0
_IDLE_LOADED_WATTS = 9.0  # extra GPU power while the weights sit in VRAM


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
                "active_hours": round(hours, 3),
                "kind": "local",
                "source": "measured",
            })
    return rows


def sample_signals(days=30):
    """What the device reader would know about John's PC besides daily kWh, for recommendations."""
    week = 7
    return {
        "measured_days": [{"date": (date.today() - timedelta(days=i)).isoformat(), "hours": 24.0}
                          for i in range(days, 0, -1)],
        "installed": [{"app": "Ollama", "name": name, "family": info["family"], "params_b": info["params_b"],
                       "quantization": info["quantization"], "size_bytes": None}
                      for name, info in LOCAL_MODELS.items() if info["params_b"]],
        "idle_loaded": [{"model": "llama3:70b", "idle_hours": _IDLE_LOADED_HOURS * week,
                         "kwh": _IDLE_LOADED_WATTS * _IDLE_LOADED_HOURS * week / 1000, "rss_mb": 40_000,
                         "days": week}],
        "cloud": None,  # John only runs local models
    }
