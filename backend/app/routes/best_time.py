from flask import current_app, jsonify

from ..services.cheap_hours import cheap_hours
from ..services.usage_store import get_clean_hours, get_hourly_usage
from . import api_bp, bill_params


@api_bp.get("/best-time")
def best_time():
    """When to run heavy AI jobs: the tariff's cheapest hours, the grid's cleanest, and the best of both."""
    use = get_hourly_usage()
    clean = get_clean_hours(use)
    info = cheap_hours(use, bill_params(), clean, current_app.config["CLEAN_WINDOW_HOURS"])
    return jsonify({**info, "use": clean["use"], "clean": {
        "configured": clean["configured"], "zone": clean["zone"], "source": clean["source"],
        "cleanest": clean["plan"] and clean["plan"]["cleanest"], "now": clean["now"]}})
