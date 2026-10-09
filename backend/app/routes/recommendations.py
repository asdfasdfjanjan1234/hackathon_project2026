from flask import jsonify

from ..services.forecasting import forecast_bill
from ..services.recommendations import build_recommendations
from ..services.usage_store import get_daily_usage
from . import api_bp, bill_params


@api_bp.get("/recommendations")
def recommendations():
    p = bill_params()
    daily = get_daily_usage()
    forecast = forecast_bill(daily, rate=p["rate"], baseline_bill=p["baseline_bill"])
    recs = build_recommendations(daily, forecast, rate=p["rate"], budget=p["budget"])
    total_savings = sum(r["monthly_savings"] for r in recs)
    return jsonify({
        "recommendations": recs,
        "forecast_bill": forecast["forecast_bill"],
        "bill_with_recommendations": round(forecast["forecast_bill"] - total_savings, 2),
    })
