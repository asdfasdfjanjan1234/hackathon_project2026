from flask import jsonify

from ..services.measurement import read_live_power
from . import api_bp


@api_bp.get("/live")
def live():
    return jsonify(read_live_power())
