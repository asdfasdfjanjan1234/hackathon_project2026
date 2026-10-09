from flask import current_app, jsonify

from ..services.forecasting import forecast_bill
from ..services.usage_store import get_daily_usage
from . import api_bp


@api_bp.get("/forecast")
def forecast():
    cfg = current_app.config
    return jsonify(forecast_bill(
        get_daily_usage(),
        rate=cfg["ELECTRICITY_RATE"],
        baseline_bill=cfg["BASELINE_BILL"],
    ))
