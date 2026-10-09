from flask import current_app, jsonify

from ..services.impact import bill_impact
from ..services.usage_store import get_daily_usage
from . import api_bp


@api_bp.get("/impact")
def impact():
    cfg = current_app.config
    return jsonify(bill_impact(
        get_daily_usage(),
        baseline_bill=cfg["BASELINE_BILL"],
        current_bill=cfg["CURRENT_BILL"],
        baseline_rate=cfg["BASELINE_RATE"],
        current_rate=cfg["ELECTRICITY_RATE"],
    ))
