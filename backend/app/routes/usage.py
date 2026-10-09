from flask import current_app, jsonify

from ..services.usage_store import get_daily_usage, summarize_by_model
from . import api_bp


@api_bp.get("/usage")
def usage():
    daily = get_daily_usage()
    rate = current_app.config["ELECTRICITY_RATE"]
    return jsonify({
        "rate_per_kwh": rate,
        "daily": daily,
        "by_model": summarize_by_model(daily, rate),
    })
