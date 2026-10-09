from flask import current_app, jsonify

from ..services.actions import annotate
from ..services.carbon import with_carbon
from ..services.outlook import outlook
from . import api_bp, bill_params


@api_bp.get("/recommendations")
def recommendations():
    p = bill_params()
    forecast, recs = outlook(p)
    cfg = current_app.config
    # co2_saved_kg: CO₂ a month each one avoids (co2_shifted_kg when it only moves work to a data center).
    recs = with_carbon(recs, p["rate"], cfg["GRID_CO2_KG_PER_KWH"], cfg["DATACENTER_CO2_KG_PER_KWH"])
    return jsonify({
        "recommendations": annotate(recs),  # `apply`: what the Apply button would do, if anything
        "forecast_bill": forecast["forecast_bill"],
        # This cycle's bill if the recommendations start tomorrow; monthly_savings is a full month.
        "bill_with_recommendations": forecast["forecast_bill_with_recommendations"],
        "monthly_savings": forecast["monthly_savings"],
        # Same combined savings as monthly_savings, in CO₂, plus what the data-center switches avoid.
        "monthly_co2_saved_kg": round(forecast["monthly_savings"] / p["rate"] * cfg["GRID_CO2_KG_PER_KWH"]
                                      + sum(r["co2_saved_kg"] or 0 for r in recs if r["scope"] == "datacenter"), 4)
                                if p["rate"] else None,
        "next_month": forecast["projections"][0],
    })
