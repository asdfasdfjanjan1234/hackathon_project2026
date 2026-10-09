from flask import jsonify

from ..services.impact import bill_impact
from ..services.usage_store import equivalence_factors, equivalents, get_daily_usage
from . import api_bp, bill_params


@api_bp.get("/impact")
def impact():
    p = bill_params()
    result = bill_impact(
        get_daily_usage(),
        baseline_bill=p["baseline_bill"],
        current_bill=p["current_bill"],
        baseline_rate=p["baseline_rate"],
        current_rate=p["rate"],
    )
    return jsonify({**result, "equivalents": equivalents(result["local_ai_kwh"]),
                    "factors": equivalence_factors()})
