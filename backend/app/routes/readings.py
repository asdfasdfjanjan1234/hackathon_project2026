from contextlib import closing

from flask import current_app, jsonify, request

from ..services import storage
from . import api_bp


@api_bp.get("/devices")
def devices():
    """Devices that have stored readings in the database."""
    database = current_app.config["DATABASE"]
    with closing(storage.connect(database)) as conn:
        found = storage.list_devices(conn)
    return jsonify({"database": "mysql" if storage.is_mysql(database) else "sqlite", "devices": found})


@api_bp.get("/readings")
def readings():
    """Stored readings, newest first. Filters: ?since=&until= (Unix seconds), ?device_id=, ?limit= (max 5000)."""
    limit = min(request.args.get("limit", type=int, default=500), 5000)
    with closing(storage.connect(current_app.config["DATABASE"])) as conn:
        rows = storage.readings(conn, since=request.args.get("since", type=float),
                                until=request.args.get("until", type=float),
                                device_id=request.args.get("device_id", type=int), limit=limit)
    return jsonify({"count": len(rows), "readings": rows})
