"""Projects this month's electricity bill from daily per-model usage."""

import calendar
from collections import defaultdict
from datetime import date


def _linear_trend(values):
    """Least-squares slope and intercept for values indexed 0..n-1."""
    n = len(values)
    if n < 2:
        return 0.0, (values[0] if values else 0.0)
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values))
    den = sum((x - mean_x) ** 2 for x in range(n))
    slope = num / den
    return slope, mean_y - slope * mean_x


def forecast_bill(daily, rate, baseline_bill, today=None):
    today = today or date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_left = days_in_month - today.day + 1

    by_model = defaultdict(list)
    for row in sorted(daily, key=lambda r: r["date"]):
        by_model[row["model"]].append(row["kwh"])

    models = []
    for model, values in by_model.items():
        slope, intercept = _linear_trend(values)
        n = len(values)
        # Project the trend forward, never below zero.
        projected = [max(0.0, intercept + slope * (n + i)) for i in range(days_in_month)]
        monthly_kwh = sum(projected)
        models.append({
            "model": model,
            "monthly_kwh": round(monthly_kwh, 2),
            "monthly_cost": round(monthly_kwh * rate, 2),
            "daily_trend_kwh": round(slope, 4),
        })

    ai_cost = sum(m["monthly_cost"] for m in models)
    return {
        "month": today.strftime("%Y-%m"),
        "days_left": days_left,
        "baseline_bill": baseline_bill,
        "ai_cost": round(ai_cost, 2),
        "forecast_bill": round(baseline_bill + ai_cost, 2),
        "by_model": sorted(models, key=lambda m: m["monthly_cost"], reverse=True),
    }
