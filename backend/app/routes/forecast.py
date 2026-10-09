from flask import jsonify

from ..services.outlook import outlook
from ..services.usage_store import equivalence_factors, equivalents
from . import api_bp, bill_params


@api_bp.get("/forecast")
def forecast():
    """This billing cycle's bill (current path and with recommendations), day by day,
    and the bills for the next 1, 3 and 12 months."""
    result, _ = outlook(bill_params())
    cycle_kwh = sum(d["ai_kwh"] for d in result["daily"])
    return jsonify({**result, "equivalents": equivalents(cycle_kwh), "factors": equivalence_factors()})
