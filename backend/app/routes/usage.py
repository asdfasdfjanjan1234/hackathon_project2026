from flask import jsonify

from ..services import storage
from ..services.usage_store import (connect, data_source, equivalence_factors, equivalents, get_daily_usage,
                                    summarize_by_model, this_device_id)
from . import api_bp, bill_params


@api_bp.get("/usage")
def usage():
    daily = get_daily_usage()
    rate = bill_params()["rate"]
    by_host, parts_by_model = [], {}
    if data_source() == "device":
        with connect() as conn:
            device_id = this_device_id(conn)
            hosts = storage.host_usage(conn, device_id=device_id)
            parts_by_model = {p.pop("model"): p for p in storage.app_part_usage(conn, device_id=device_id)}
        by_host = [{**h, "cost": round(h["kwh"] * rate, 4)} for h in hosts]
    on_bill = sum(r["kwh"] for r in daily if r.get("source", "measured") == "measured")
    return jsonify({
        "data_source": data_source(),
        "rate_per_kwh": rate,
        "daily": daily,
        "by_model": summarize_by_model(daily, rate),
        "by_host": by_host,
        # kWh per model split into CPU, GPU and memory (this device's readings only).
        "parts_by_model": parts_by_model,
        "equivalents": equivalents(on_bill),
        "factors": equivalence_factors(),
    })
