"""Rule-based recommendations: STOP, SWITCH or REDUCE, each with expected savings."""

from .models_catalog import MODELS


def build_recommendations(daily, forecast, rate, budget):
    recs = []
    by_model = {m["model"]: m for m in forecast["by_model"]}

    # SWITCH: a big local model that has a smaller alternative.
    for model, m in by_model.items():
        alt = MODELS.get(model, {}).get("smaller_alternative")
        if not alt:
            continue
        ratio = MODELS[alt]["avg_watts"] / MODELS[model]["avg_watts"]
        # Assume half of this model's use could move to the smaller one.
        savings = m["monthly_cost"] * 0.5 * (1 - ratio)
        recs.append({
            "action": "SWITCH",
            "model": model,
            "message": f"Use {alt} instead of {model} for simple tasks. It draws about "
                       f"{1 / ratio:.1f}× less power.",
            "monthly_savings": round(savings, 2),
        })

    # REDUCE: the top consumer if the forecast goes over budget.
    if forecast["forecast_bill"] > budget and forecast["by_model"]:
        top = forecast["by_model"][0]
        over = forecast["forecast_bill"] - budget
        recs.append({
            "action": "REDUCE",
            "model": top["model"],
            "message": f"Your forecast is ₱{over:,.0f} over your ₱{budget:,.0f} budget. "
                       f"{top['model']} is your biggest consumer; cut its use by 25%.",
            "monthly_savings": round(top["monthly_cost"] * 0.25, 2),
        })

    # STOP: a model whose usage keeps growing fastest.
    growing = [m for m in forecast["by_model"] if m["daily_trend_kwh"] > 0]
    if growing:
        fastest = max(growing, key=lambda m: m["daily_trend_kwh"])
        if fastest["model"] not in {r["model"] for r in recs}:
            recs.append({
                "action": "STOP",
                "model": fastest["model"],
                "message": f"{fastest['model']} usage is growing fastest. Stop using it for "
                           f"non-essential jobs.",
                "monthly_savings": round(fastest["monthly_cost"] * 0.5, 2),
            })

    return sorted(recs, key=lambda r: r["monthly_savings"], reverse=True)
