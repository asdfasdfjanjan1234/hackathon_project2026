from flask import jsonify

from ..services import storage
from ..services.model_usage import model_usage
from ..services.models_catalog import REFERENCE
from ..services.usage_store import connect, summarize_by_model, this_device_id
from . import api_bp, bill_params


@api_bp.get("/models")
def models():
    """Models found on this device: tokens and estimated data-center energy from the apps'
    logs, next to the device energy measured while each model was the app's active one."""
    data = model_usage()
    rate = bill_params()["rate"]
    with connect() as conn:
        daily = storage.daily_usage(conn, device_id=this_device_id(conn))
    device = {m["model"]: m for m in summarize_by_model(daily, rate)}
    for m in data["models"]:
        measured = device.get(f"{m['app']} · {m['model']}")
        m["device_kwh"] = measured and measured["kwh"]
        m["device_cost"] = measured and measured["cost"]
    return jsonify({**data, "reference": REFERENCE,
                    "note": "Data-center energy is estimated from list prices and is not on your bill."})
