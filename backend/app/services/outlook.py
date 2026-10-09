"""The bill forecast and the recommendations together, since each needs the other:
recommendations come from the forecast, and the "with recommendations" path of the
forecast applies their savings."""

from .forecasting import forecast_bill
from .recommendations import build_recommendations, reductions
from .usage_store import get_daily_usage, get_signals


def outlook(params, today=None):
    daily, signals = get_daily_usage(), get_signals()
    common = dict(rate=params["rate"], baseline_bill=params["baseline_bill"], today=today,
                  cycle_start_day=params["cycle_start_day"], measured_days=signals.get("measured_days"),
                  budget=params["budget"])
    forecast = forecast_bill(daily, **common)
    recs = build_recommendations(daily, forecast, params["rate"], params["budget"], signals, today)
    saved = reductions(recs, forecast)
    forecast = forecast_bill(daily, **common, reductions=saved)
    forecast["monthly_savings"] = round(sum(m["monthly_cost"] * saved.get(m["model"], 0.0)
                                            for m in forecast["by_model"]), 2)
    return forecast, recs
