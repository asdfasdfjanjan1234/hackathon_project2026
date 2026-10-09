from contextlib import closing

from flask import current_app, jsonify

from ..services import storage
from ..services.usage_store import data_source, get_daily_usage, summarize_by_model
from . import api_bp, bill_params


@api_bp.get("/usage")
def usage():
    daily = get_daily_usage()
    rate = bill_params()["rate"]
    by_host = []
    if data_source() == "device":
        with closing(storage.connect(current_app.config["DB_PATH"])) as conn:
            by_host = [{**h, "cost": round(h["kwh"] * rate, 4)} for h in storage.host_usage(conn)]
    return jsonify({
        "data_source": data_source(),
        "rate_per_kwh": rate,
        "daily": daily,
        "by_model": summarize_by_model(daily, rate),
        "by_host": by_host,
    })
