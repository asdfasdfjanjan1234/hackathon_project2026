from flask import current_app, jsonify, request

from ..services.alerts import build_alerts
from ..services.assistant import own_label
from ..services.outlook import snapshot
from . import api_bp, bill_params


@api_bp.get("/alerts")
def alerts():
    """What's worth telling the user now: budget overruns, savings, and notes on the readings.
    Rule-based, so it works with the assistant off."""
    snap = snapshot(bill_params(), request.args.get("range", "30d"))
    return jsonify({"alerts": build_alerts(snap, own_label(current_app.config["ASSISTANT_MODEL"]))})
