from datetime import date, timedelta

from flask import jsonify, request

from ..services import storage
from ..services.usage_store import (connect, data_source, equivalence_factors, equivalents, get_daily_usage,
                                    summarize_by_model, this_device_id, usage_window)
from . import api_bp, bill_params


@api_bp.get("/usage")
def usage():
    """Usage in the 7D, 30D or MTD window (?range=7d|30d|month, default 30d)."""
    # The sample data's last day is yesterday; this device's readings run through today.
    end = date.today() - timedelta(days=1) if data_source() == "sample" else None
    window = usage_window(request.args.get("range", "30d"), end=end)
    since_ts = window.pop("since_ts")
    # 32 days back covers a full month to date as well as the rolling windows.
    daily = [r for r in get_daily_usage(days=32) if window["start"] <= r["date"] <= window["end"]]
    rate = bill_params()["rate"]
    by_host, parts_by_model = [], {}
    if data_source() == "device":
        with connect() as conn:
            device_id = this_device_id(conn)
            hosts = storage.host_usage(conn, device_id=device_id, since=since_ts)
            parts_by_model = {p.pop("model"): p for p in storage.app_part_usage(conn, device_id=device_id,
                                                                                 since=since_ts)}
        by_host = [{**h, "cost": round(h["kwh"] * rate, 4)} for h in hosts]
    on_bill = sum(r["kwh"] for r in daily if r.get("source", "measured") == "measured")
    return jsonify({
        "data_source": data_source(),
        "rate_per_kwh": rate,
        "window": window,
        "window_days": window["days"],
        "daily": daily,
        "by_model": summarize_by_model(daily, rate),
        "by_host": by_host,
        # kWh per model split into CPU, GPU and memory (this device's readings only).
        "parts_by_model": parts_by_model,
        "equivalents": equivalents(on_bill),
        "factors": equivalence_factors(),
    })
