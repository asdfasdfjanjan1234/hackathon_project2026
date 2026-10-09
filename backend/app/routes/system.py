from contextlib import closing

from flask import current_app, jsonify

from ..services import storage
from ..services.measurement import default_sensors
from . import api_bp


@api_bp.get("/system")
def system():
    """Detected OS and hardware, which sensor each component uses, and daily kWh per component."""
    sensors = default_sensors()
    with closing(storage.connect(current_app.config["DB_PATH"])) as conn:
        daily = storage.daily_component_usage(conn)
    return jsonify({"system": sensors.system, "sensors": sensors.sources(), "daily_components": daily})
