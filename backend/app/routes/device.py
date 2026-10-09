from flask import current_app, jsonify, request

from ..services.device_reader import reader
from ..services.measurement import default_sensors
from ..services.usage_store import data_source
from . import api_bp


def _status():
    cfg = current_app.config
    return {**reader.status(cfg["DB_PATH"]), "data_source": data_source()}


@api_bp.post("/device/start")
def device_start():
    """Detect this device's OS and hardware, then start measuring AI apps every 2 s."""
    sensors = default_sensors()  # detection runs once and is shared with the reader
    started = reader.start(current_app.config["DB_PATH"])
    current_app.config["DATA_SOURCE"] = "device"
    return jsonify({**_status(), "started": started, "system": sensors.system, "sensors": sensors.sources()})


@api_bp.post("/device/stop")
def device_stop():
    reader.stop()
    return jsonify(_status())


@api_bp.get("/device/status")
def device_status():
    return jsonify(_status())


@api_bp.post("/device/source")
def device_source():
    """Switch the dashboard between this device's data and the sample data (John's gaming PC)."""
    source = (request.get_json(silent=True) or {}).get("source")
    if source not in ("device", "sample"):
        return jsonify({"error": "source must be 'device' or 'sample'"}), 400
    current_app.config["DATA_SOURCE"] = source
    return jsonify(_status())
