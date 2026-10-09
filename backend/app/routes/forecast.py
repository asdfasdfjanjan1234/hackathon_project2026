from flask import jsonify

from ..services.arima_forecast import accuracy
from ..services.outlook import outlook
from ..services.usage_store import connect, equivalence_factors, equivalents, this_device_id
from . import api_bp, bill_params


@api_bp.get("/forecast")
def forecast():
    """This billing cycle's bill (current path and with recommendations), day by day,
    and the bills for the next 1, 3 and 12 months."""
    result, _ = outlook(bill_params())
    cycle_kwh = sum(d["ai_kwh"] for d in result["daily"])
    return jsonify({**result, "equivalents": equivalents(cycle_kwh), "factors": equivalence_factors()})


@api_bp.get("/forecast/accuracy")
def forecast_accuracy():
    """The fine-tuned ARIMA models scored on their held-out windows as an "in use / idle" classifier:
    accuracy, precision, recall and F1, next to simple baselines."""
    with connect() as conn:
        device_id = this_device_id(conn)
    return jsonify(accuracy(device_id))
