from flask import jsonify

from ..services.forecasting import forecast_bill
from ..services.usage_store import get_daily_usage
from . import api_bp, bill_params


@api_bp.get("/forecast")
def forecast():
    p = bill_params()
    result = forecast_bill(get_daily_usage(), rate=p["rate"], baseline_bill=p["baseline_bill"])
    return jsonify({**result, "budget": p["budget"]})
