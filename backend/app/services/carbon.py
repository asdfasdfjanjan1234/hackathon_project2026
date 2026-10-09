"""Carbon footprint of AI use: on this device, and in the data centers that run cloud models.

Two grids, two factors:
  device      kWh measured on this machine x this grid's factor (GRID_CO2_KG_PER_KWH)
  datacenter  estimated data-center kWh of cloud models x the provider grid's factor
              (DATACENTER_CO2_KG_PER_KWH). Estimated from tokens, so it ranks rather than measures.

The cycle and 12-month figures come from the bill forecast, so "with recommendations"
uses the same savings as the bill. Moving work to the cloud ("cloud" rule) doesn't avoid
CO2, it moves it to another grid, so that recommendation reports CO2 shifted, not saved.
"""

from collections import defaultdict
from datetime import date, timedelta

TREE_KG_PER_YEAR = 21.77  # CO2 one mature tree absorbs in a year (1.81 kg a month, as in usage_store)
SHIFTED_RULES = {"cloud"}


def _kg(x):
    return round(x, 4)


def rec_co2(rec, rate, grid, datacenter):
    """Monthly CO2 a recommendation avoids: {co2_saved_kg} or, for moving work to the cloud,
    {co2_shifted_kg} (the CO2 leaves this grid but is emitted on the data center's)."""
    if rec["scope"] == "datacenter":
        return {"co2_saved_kg": _kg((rec.get("wh_saved") or 0) / 1000 * datacenter)}
    kwh = rec["monthly_savings"] / rate if rate else 0.0
    if rec["rule"] in SHIFTED_RULES:
        return {"co2_saved_kg": None, "co2_shifted_kg": _kg(kwh * grid)}
    return {"co2_saved_kg": _kg(kwh * grid)}


def with_carbon(recs, rate, grid, datacenter):
    return [{**r, **rec_co2(r, rate, grid, datacenter)} for r in recs]


def _window_days(start, end):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    return [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]


def carbon_report(device_daily, cloud_daily, forecast, recs, window, rate, grid, datacenter, budget_kg):
    """device_daily: storage.daily_usage rows (measured kWh). cloud_daily: model_usage daily rows
    (estimated datacenter_wh). Both already cut to `window`."""
    days = _window_days(window["start"], window["end"])
    per_day = {d: {"date": d, "device_kg": 0.0, "datacenter_kg": 0.0} for d in days}
    models = defaultdict(lambda: {"kwh": 0.0, "co2_kg": 0.0, "active_hours": 0.0})

    for r in device_daily:
        kg = r["kwh"] * grid
        if r["date"] in per_day:
            per_day[r["date"]]["device_kg"] += kg
        m = models[(r["model"], "device")]
        m["kwh"] += r["kwh"]
        m["co2_kg"] += kg
        m["active_hours"] += r.get("active_hours") or 0.0
    for r in cloud_daily:
        kwh = (r.get("datacenter_wh") or 0) / 1000
        kg = kwh * datacenter
        if r["date"] in per_day:
            per_day[r["date"]]["datacenter_kg"] += kg
        m = models[(f"{r['app']} · {r['model']}", "datacenter")]
        m["kwh"] += kwh
        m["co2_kg"] += kg

    device_kg = sum(d["device_kg"] for d in per_day.values())
    dc_kg = sum(d["datacenter_kg"] for d in per_day.values())
    total_kg = device_kg + dc_kg
    by_model = sorted(
        ({"model": model, "scope": scope, "kwh": round(m["kwh"], 6), "co2_kg": _kg(m["co2_kg"]),
          "share": round(m["co2_kg"] / total_kg, 3) if total_kg else 0.0,
          # CO2 per hour of use: how carbon-heavy a model is to run, independent of how much it's used.
          "g_per_active_hour": round(m["co2_kg"] * 1000 / m["active_hours"], 1) if m["active_hours"] >= 0.1 else None}
         for (model, scope), m in models.items() if m["kwh"] > 0),
        key=lambda m: m["co2_kg"], reverse=True)

    # This billing cycle: device CO2 follows the bill forecast; cloud CO2 carries on at the window's daily average.
    dc_per_day = dc_kg / len(days) if days else 0.0
    cycle_days = forecast["cycle"]["days"]
    cycle_device = sum(d["ai_kwh"] for d in forecast["daily"]) * grid
    cycle_device_recs = (forecast["ai_cost_with_recommendations"] / rate * grid) if rate else cycle_device
    future_share = max(forecast["days_left"] - 1, 0) / cycle_days  # recommendations start tomorrow
    dc_saved_month = sum(r.get("co2_saved_kg") or 0 for r in recs if r["scope"] == "datacenter")
    cycle_dc = dc_per_day * cycle_days
    cycle_dc_recs = max(cycle_dc - dc_saved_month * future_share, 0.0)
    projected, projected_recs = cycle_device + cycle_dc, cycle_device_recs + cycle_dc_recs

    budget = None
    if budget_kg > 0:
        cum, exceeded = 0.0, None
        for d in forecast["daily"]:
            cum += d["ai_kwh"] * grid + dc_per_day
            if cum > budget_kg:
                exceeded = d["date"]
                break
        status = ("under" if projected <= budget_kg else
                  "fixed_by_recommendations" if projected_recs <= budget_kg else "over")
        budget = {"kg": budget_kg, "status": status, "exceeded_on": exceeded,
                  "used_share": round(projected / budget_kg, 3),
                  "used_share_with_recommendations": round(projected_recs / budget_kg, 3)}

    # A year ahead, from the forecast's 12-month projection.
    year = forecast["projections"][-1]
    year_kwh_recs = ((year["bill_with_recommendations"] - year["months"] * forecast["baseline_bill"]) / rate
                     if rate else year["ai_kwh"])
    year_dc = dc_per_day * 365
    year_kg = year["ai_kwh"] * grid + year_dc
    year_kg_recs = year_kwh_recs * grid + max(year_dc - dc_saved_month * 12, 0.0)
    avoided = max(year_kg - year_kg_recs, 0.0)

    actions = sorted((r for r in recs if (r.get("co2_saved_kg") or 0) > 0 and not r["alternative"]),
                     key=lambda r: r["co2_saved_kg"], reverse=True)

    return {
        "window": window,
        "factors": {"device_kg_per_kwh": grid, "datacenter_kg_per_kwh": datacenter},
        "totals": {"device_kg": _kg(device_kg), "datacenter_kg": _kg(dc_kg), "total_kg": _kg(total_kg),
                   "device_kwh": round(sum(r["kwh"] for r in device_daily), 6),
                   "datacenter_kwh": round(sum((r.get("datacenter_wh") or 0) for r in cloud_daily) / 1000, 6),
                   "trees_month": round(total_kg / (TREE_KG_PER_YEAR / 12) * (30 / len(days)), 1) if days else 0.0},
        "daily": [{**d, "device_kg": _kg(d["device_kg"]), "datacenter_kg": _kg(d["datacenter_kg"])}
                  for d in per_day.values()],
        "by_model": by_model,
        "cycle": {"start": forecast["cycle"]["start"], "end": forecast["cycle"]["end"],
                  "projected_kg": _kg(projected), "projected_kg_with_recommendations": _kg(projected_recs),
                  "device_kg": _kg(cycle_device), "datacenter_kg": _kg(cycle_dc)},
        "budget": budget,
        "year": {"projected_kg": round(year_kg, 2), "projected_kg_with_recommendations": round(year_kg_recs, 2),
                 "avoided_kg": round(avoided, 2), "trees_equivalent": round(avoided / TREE_KG_PER_YEAR, 1)},
        "top_actions": [{"action": r["action"], "rule": r["rule"], "model": r["model"], "message": r["message"],
                         "co2_saved_kg": r["co2_saved_kg"], "monthly_savings": r["monthly_savings"],
                         "scope": r["scope"]} for r in actions[:3]],
    }
