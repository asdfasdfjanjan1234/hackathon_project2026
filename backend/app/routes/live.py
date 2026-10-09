from contextlib import closing

from flask import current_app, jsonify

from ..services import storage
from ..services.measurement import read_live_power
from . import api_bp


@api_bp.get("/live")
def live():
    with closing(storage.connect(current_app.config["DATABASE"])) as conn:
        latest = storage.latest_sample(conn)
    # Without the collector running, fall back to a direct reading (total watts only).
    return jsonify(latest or read_live_power())
