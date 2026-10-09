from flask import current_app, jsonify, request

from ..services.carbon import with_carbon
from ..services.outlook import carbon_outlook, outlook
from ..services.usage_store import equivalence_factors, get_clean_hours
from . import api_bp, bill_params


@api_bp.get("/carbon")
def carbon():
    """CO₂ from AI use in the 7D, 30D or MTD window (?range=), on this device and in cloud data
    centers, plus this cycle's and next year's CO₂ with and without the recommendations."""
    cfg = current_app.config
    p = bill_params()
    forecast, recs = outlook(p)
    recs = with_carbon(recs, p["rate"], cfg["GRID_CO2_KG_PER_KWH"], cfg["DATACENTER_CO2_KG_PER_KWH"])
    report = carbon_outlook(p, forecast, recs, request.args.get("range", "30d"))
    return jsonify({**report, "factors": {**report["factors"], **equivalence_factors(),
                                          "datacenter_source": cfg["DATACENTER_CO2_SOURCE"]},
                    # The grid's cleanest hours and this device's AI use by hour of day.
                    "clean_hours": get_clean_hours()})
