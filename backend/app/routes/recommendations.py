from flask import jsonify

from ..services.actions import annotate
from ..services.outlook import outlook
from . import api_bp, bill_params


@api_bp.get("/recommendations")
def recommendations():
    forecast, recs = outlook(bill_params())
    return jsonify({
        "recommendations": annotate(recs),  # `apply`: what the Apply button would do, if anything
        "forecast_bill": forecast["forecast_bill"],
        # This cycle's bill if the recommendations start tomorrow; monthly_savings is a full month.
        "bill_with_recommendations": forecast["forecast_bill_with_recommendations"],
        "monthly_savings": forecast["monthly_savings"],
        "next_month": forecast["projections"][0],
    })
