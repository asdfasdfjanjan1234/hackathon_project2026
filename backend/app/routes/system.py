from flask import jsonify

from ..services import storage
from ..services.measurement import default_sensors
from ..services.usage_store import connect, this_device_id
from . import api_bp


@api_bp.get("/system")
def system():
    """Detected OS and hardware, which sensor each component uses, and daily kWh per component."""
    sensors = default_sensors()
    with connect() as conn:
        daily = storage.daily_component_usage(conn, device_id=this_device_id(conn))
    return jsonify({"system": sensors.system, "sensors": sensors.sources(), "daily_components": daily})
