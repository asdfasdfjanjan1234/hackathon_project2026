from flask import jsonify, request

from ..services import storage, validation
from ..services.usage_store import connect, this_device_id
from . import api_bp


def _state(conn, device_id):
    checks = [validation.describe(c) for c in storage.meter_checks(conn, device_id)]
    return {"checks": checks, "summary": validation.summary(checks),
            "running": next((c for c in checks if c["open"]), None), "spot_window_s": validation.SPOT_WINDOW_S}


@api_bp.get("/validation")
def validation_list():
    """Wall-meter checks of our whole-machine readings, and the average difference."""
    with connect() as conn:
        return jsonify(_state(conn, this_device_id(conn)))


def _run(step):
    value = (request.get_json(silent=True) or {}).get("value")
    try:
        value = None if value is None else float(value)
    except (TypeError, ValueError):
        return jsonify({"error": "value must be a number"}), 400
    with connect() as conn:
        device_id = this_device_id(conn)
        try:
            step(conn, device_id, value)
        except validation.CheckError as e:
            return jsonify({"error": str(e)}), 409
        return jsonify(_state(conn, device_id))


@api_bp.post("/validation/watts")
def validation_watts():
    """{"value": watts the meter shows now}"""
    return _run(validation.spot_check)


@api_bp.post("/validation/start")
def validation_start():
    """{"value": the meter's kWh counter at the start}"""
    return _run(validation.start_window)


@api_bp.post("/validation/finish")
def validation_finish():
    """{"value": the meter's kWh counter at the end}"""
    return _run(validation.finish_window)


@api_bp.delete("/validation/<int:check_id>")
def validation_delete(check_id):
    with connect() as conn:
        storage.delete_meter_check(conn, check_id)
        return jsonify(_state(conn, this_device_id(conn)))
