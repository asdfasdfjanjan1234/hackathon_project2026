from flask import current_app, jsonify

from ..services.forecasting import forecast_bill
from ..services.recommendations import build_recommendations
from ..services.usage_store import get_daily_usage
from . import api_bp


@api_bp.get("/recommendations")
def recommendations():
    cfg = current_app.config
    daily = get_daily_usage()
    forecast = forecast_bill(daily, rate=cfg["ELECTRICITY_RATE"], baseline_bill=cfg["BASELINE_BILL"])
    recs = build_recommendations(
        daily,
        forecast,
        rate=cfg["ELECTRICITY_RATE"],
        budget=cfg["MONTHLY_BUDGET"],
    )
    total_savings = sum(r["monthly_savings"] for r in recs)
    return jsonify({
        "recommendations": recs,
        "forecast_bill": forecast["forecast_bill"],
        "bill_with_recommendations": round(forecast["forecast_bill"] - total_savings, 2),
    })
