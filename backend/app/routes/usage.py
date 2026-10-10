import csv
import io

from flask import Response, jsonify, request

from ..services import storage
from ..services.usage_log import CSV_COLUMNS, SLOTS, usage_log
from ..services.usage_store import (connect, equivalence_factors, equivalents, get_daily_usage,
                                    summarize_by_model, this_device_id, usage_window)
from . import api_bp, bill_params


@api_bp.get("/usage")
def usage():
    """Usage in the 7D, 30D or MTD window (?range=7d|30d|month, default 30d)."""
    window = usage_window(request.args.get("range", "30d"))
    since_ts = window.pop("since_ts")
    # 32 days back covers a full month to date as well as the rolling windows.
    daily = [r for r in get_daily_usage(days=32) if window["start"] <= r["date"] <= window["end"]]
    rate = bill_params()["rate"]
    with connect() as conn:
        device_id = this_device_id(conn)
        hosts = storage.host_usage(conn, device_id=device_id, since=since_ts)
        parts_by_model = {p.pop("model"): p for p in storage.app_part_usage(conn, device_id=device_id,
                                                                             since=since_ts)}
    by_host = [{**h, "cost": round(h["kwh"] * rate, 4)} for h in hosts]
    on_bill = sum(r["kwh"] for r in daily if r.get("source", "measured") == "measured")
    return jsonify({
        "rate_per_kwh": rate,
        "window": window,
        "window_days": window["days"],
        "daily": daily,
        "by_model": summarize_by_model(daily, rate),
        "by_host": by_host,
        # kWh per model split into CPU, GPU and memory.
        "parts_by_model": parts_by_model,
        "equivalents": equivalents(on_bill),
        "factors": equivalence_factors(),
    })


@api_bp.get("/usage/log")
def usage_log_route():
    """Timestamped usage records (IDE, app, model, effort, watts) and their energy added up by
    date, IDE, app, model and effort, for the 7D, 30D or MTD window.

    ?slot=60|900|3600 seconds per record (default 900), ?limit= records, newest first (default
    200, max 2000), ?format=csv for every record in the window as a file.
    """
    window = usage_window(request.args.get("range", "30d"))
    since_ts = window.pop("since_ts")
    slot_s = request.args.get("slot", type=int, default=900)
    if slot_s not in SLOTS:
        slot_s = 900
    as_csv = request.args.get("format") == "csv"
    limit = 100_000 if as_csv else min(max(request.args.get("limit", type=int, default=200), 1), 2000)
    rate = bill_params()["rate"]
    with connect() as conn:
        device_id = this_device_id(conn)
        daily = storage.usage_records(conn, since_ts, device_id=device_id)
        # One more than asked for, to know whether older records were left out.
        slots = storage.usage_records(conn, since_ts, device_id=device_id, slot_s=slot_s, limit=limit + 1)
    log = usage_log(daily, slots[:limit], rate)
    if as_csv:
        out = io.StringIO()
        writer = csv.DictWriter(out, CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(log["records"])
        return Response(out.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": f"attachment; filename=usage-log-{window['start']}-to-{window['end']}.csv"})
    return jsonify({"rate_per_kwh": rate, "window": window, "slot_s": slot_s,
                    "records_truncated": len(slots) > limit, **log})
