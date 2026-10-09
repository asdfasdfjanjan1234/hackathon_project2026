from flask import jsonify

from ..services.impact import bill_impact
from ..services.usage_store import get_daily_usage
from . import api_bp, bill_params


@api_bp.get("/impact")
def impact():
    p = bill_params()
    return jsonify(bill_impact(
        get_daily_usage(),
        baseline_bill=p["baseline_bill"],
        current_bill=p["current_bill"],
        baseline_rate=p["baseline_rate"],
        current_rate=p["rate"],
    ))
