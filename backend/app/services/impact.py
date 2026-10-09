"""Answers: did AI usage increase the electricity bill, and by how much?

The bill increase is split into three parts:
  rate effect        - the price per kWh changed (nothing to do with usage)
  AI effect          - measured local-model kWh x current rate
  other usage effect - whatever consumption increase the AI energy cannot explain

Cloud models are reported separately: their electricity is billed to the
provider's data center, not to the user, so it is never counted in the bill.
"""


def _verdict(share):
    if share is None:
        return "no_increase"
    if share >= 0.5:
        return "major"
    if share >= 0.2:
        return "contributing"
    if share > 0:
        return "minor"
    return "none"


def bill_impact(daily, baseline_bill, current_bill, baseline_rate, current_rate):
    local_kwh = sum(r["kwh"] for r in daily if r["source"] == "measured")
    cloud_kwh = sum(r["kwh"] for r in daily if r["source"] == "estimated")

    increase = current_bill - baseline_bill
    baseline_kwh = baseline_bill / baseline_rate
    rate_effect = baseline_kwh * (current_rate - baseline_rate)
    consumption_effect = increase - rate_effect

    ai_cost = local_kwh * current_rate
    ai_effect = max(0.0, min(ai_cost, consumption_effect))
    other_effect = consumption_effect - ai_effect

    share = ai_effect / increase if increase > 0 else None
    return {
        "baseline_bill": baseline_bill,
        "current_bill": current_bill,
        "increase": round(increase, 2),
        "rate_effect": round(rate_effect, 2),
        "ai_effect": round(ai_effect, 2),
        "other_effect": round(other_effect, 2),
        "ai_share": None if share is None else round(share, 3),
        "verdict": _verdict(share),
        "local_ai_kwh": round(local_kwh, 6),
        "cloud_ai_kwh_estimated": round(cloud_kwh, 6),
        "note": "Cloud AI energy is billed to the data center, not to the user, so it is excluded from the bill.",
    }
