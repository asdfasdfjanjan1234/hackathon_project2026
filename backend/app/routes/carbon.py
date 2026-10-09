from flask import current_app, jsonify, request

from ..services.carbon import carbon_report, with_carbon
from ..services.model_usage import model_usage
from ..services.outlook import outlook
from ..services.usage_store import equivalence_factors, get_daily_usage, usage_window
from . import api_bp, bill_params


@api_bp.get("/carbon")
def carbon():
    """CO₂ from AI use in the 7D, 30D or MTD window (?range=), on this device and in cloud data
    centers, plus this cycle's and next year's CO₂ with and without the recommendations."""
    cfg = current_app.config
    p = bill_params()
    grid, datacenter = cfg["GRID_CO2_KG_PER_KWH"], cfg["DATACENTER_CO2_KG_PER_KWH"]
    window = usage_window(request.args.get("range", "30d"))
    window.pop("since_ts")

    def in_window(r):
        return window["start"] <= r["date"] <= window["end"]

    forecast, recs = outlook(p)
    report = carbon_report(
        [r for r in get_daily_usage(days=32) if in_window(r)],
        [r for r in model_usage(days=32)["daily"] if in_window(r)],
        forecast,
        with_carbon(recs, p["rate"], grid, datacenter),
        window,
        rate=p["rate"],
        grid=grid,
        datacenter=datacenter,
        budget_kg=request.args.get("carbon_budget", type=float, default=cfg["CARBON_BUDGET_KG"]),
    )
    return jsonify({**report, "factors": {**report["factors"], **equivalence_factors(),
                                          "datacenter_source": cfg["DATACENTER_CO2_SOURCE"]}})
