from flask import jsonify

from ..services import storage
from ..services.usage_store import (connect, data_source, equivalence_factors, equivalents, get_daily_usage,
                                    summarize_by_model, this_device_id)
from . import api_bp, bill_params


@api_bp.get("/usage")
def usage():
    daily = get_daily_usage()
    rate = bill_params()["rate"]
    by_host = []
    if data_source() == "device":
        with connect() as conn:
            hosts = storage.host_usage(conn, device_id=this_device_id(conn))
        by_host = [{**h, "cost": round(h["kwh"] * rate, 4)} for h in hosts]
    on_bill = sum(r["kwh"] for r in daily if r.get("source", "measured") == "measured")
    return jsonify({
        "data_source": data_source(),
        "rate_per_kwh": rate,
        "daily": daily,
        "by_model": summarize_by_model(daily, rate),
        "by_host": by_host,
        "equivalents": equivalents(on_bill),
        "factors": equivalence_factors(),
    })
