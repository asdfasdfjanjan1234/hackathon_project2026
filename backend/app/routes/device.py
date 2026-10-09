from flask import current_app, jsonify

from ..services.device_reader import reader
from ..services.measurement import default_sensors
from . import api_bp


def _status():
    return reader.status(current_app.config["DATABASE"])


@api_bp.before_app_request
def resume_reading():
    """Reading was on before the backend restarted (e.g. the debug reloader): carry on."""
    reader.resume(current_app.config["DATABASE"])


@api_bp.post("/device/start")
def device_start():
    """Detect this device's OS and hardware, then start measuring AI apps every 2 s."""
    sensors = default_sensors()  # detection runs once and is shared with the reader
    started = reader.start(current_app.config["DATABASE"])
    return jsonify({**_status(), "started": started, "system": sensors.system, "sensors": sensors.sources()})


@api_bp.post("/device/stop")
def device_stop():
    reader.stop(current_app.config["DATABASE"])
    return jsonify(_status())


@api_bp.get("/device/status")
def device_status():
    return jsonify(_status())

