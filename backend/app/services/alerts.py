"""What's worth telling the user right now, from the same numbers the dashboard shows.

Rule-based, like the recommendations: no model is involved, so the bell works with the
assistant off. The assistant puts these into words (assistant.py).

  alert   needs action: the bill or the carbon budget will be passed even with the recommendations
  warn    will be passed unless the recommendations are applied
  tip     a recommendation that saves money or CO2
  info    something that explains the numbers (reader off, estimated power, a rough forecast)

Each alert: {id, level, title, text, view}. `view` is the dashboard view that shows it.
The id stays the same for as long as the condition holds, so it's announced once.
"""

from .models_catalog import local_name

LEVELS = ["alert", "warn", "tip", "info"]
MAX_TIPS = 3
AI_HEAVY_SHARE = 0.5   # AI apps above this share of the computer's power, and ...
AI_HEAVY_WATTS = 10.0  # ... above this many watts, is worth a note
ROUGH_FORECAST_DAYS = 3

# Recommendation rule -> title. {name} is the model without its app prefix, {app} the app alone.
TIP_TITLES = {
    "smaller": "A smaller model would do for part of {name}'s work",
    "quantized": "{name} runs at a heavy quantization",
    "idle": "{name} stayed loaded while idle",
    "per hour": "{name} costs the most per hour",
    "tool runs": "{app}'s tool runs use more energy than the agent",
    "growing": "{name} use is growing fastest",
    "cheap hours": "AI is running in peak hours",
    "clean hours": "AI is running when the grid is dirtier",
    "big cloud": "Most cloud tokens go to a large model",
}


def _alert(alert_id, level, title, text, view):
    return {"id": alert_id, "level": level, "title": title, "text": text, "view": view}


def _budget(snap):
    rec = next((r for r in snap["recommendations"] if r["rule"] == "budget"), None)
    if not rec:
        return []
    forecast = snap["forecast"]
    fixed = forecast["forecast_bill_with_recommendations"] <= forecast["budget"]
    return [_alert("budget", "warn" if fixed else "alert", "The bill forecast is over your budget",
                   rec["message"], "analytics")]


def _carbon_budget(snap):
    budget = snap["carbon"].get("budget")
    if not budget or budget["status"] == "under":
        return []
    cycle = snap["carbon"]["cycle"]
    when = f", passing it on {budget['exceeded_on']}" if budget.get("exceeded_on") else ""
    text = (f"AI use is heading for {cycle['projected_kg']:,.1f} kg CO₂ this billing cycle against a carbon budget "
            f"of {budget['kg']:g} kg{when}.")
    if budget["status"] == "fixed_by_recommendations":
        text += f" The recommendations bring it to {cycle['projected_kg_with_recommendations']:,.1f} kg, under the budget."
        return [_alert("carbon-budget", "warn", "AI use is over your carbon budget", text, "carbon")]
    return [_alert("carbon-budget", "alert", "AI use is over your carbon budget",
                   text + " Most of it has to come from using large cloud models less.", "carbon")]


def _tips(snap):
    out = []
    for r in snap["recommendations"]:
        saves = r["monthly_savings"] > 0 or (r.get("co2_saved_kg") or 0) > 0
        if r["rule"] not in TIP_TITLES or r["alternative"] or not saves:
            continue
        title = TIP_TITLES[r["rule"]].format(name=local_name(r["model"]), app=r["model"].split(" · ")[0])
        out.append(_alert(f"tip:{r['rule']}:{r['model']}", "tip", title, r["message"], "recommendations"))
    return out[:MAX_TIPS]


def _live(snap, own_model):
    live = snap["live"]
    if live.get("source") != "collector":
        return [_alert("reader-off", "info", "The device reader is off",
                       "The live figure is the whole computer only. Start the reader in This Device to see which "
                       "AI apps use the power, and to keep the forecast up to date.", "device")]
    out = []
    # The assistant's own model is left out: its replies would otherwise set off this note.
    ai = sum(a.get("watts") or 0 for a in live.get("apps") or [] if a.get("name") != own_model)
    total = live.get("watts") or 0
    if total and ai >= AI_HEAVY_WATTS and ai / total >= AI_HEAVY_SHARE:
        out.append(_alert("ai-heavy", "info", "AI is most of this computer's power right now",
                          f"AI apps draw {ai:,.1f} W of the {total:,.1f} W this computer is using "
                          f"({ai / total:.0%}).", "dashboard"))
    if live.get("estimated"):
        out.append(_alert("estimated", "info", "Power is estimated, not measured",
                          "No power sensor can be read right now, so watts are calculated from CPU and GPU use "
                          "with the formula fitted to this computer.", "device"))
    return out


def _coverage(snap):
    cov = snap["forecast"].get("coverage") or {}
    days = cov.get("days_measured") or 0
    if days >= ROUGH_FORECAST_DAYS:
        return []
    if not days:
        return [_alert("coverage", "info", "No readings yet",
                       "The forecast has nothing to go on until the device reader has run while you use AI.",
                       "device")]
    return [_alert("coverage", "info", "The forecast is still rough",
                   f"It's based on {cov.get('hours_measured') or 0:,.1f} hours of readings over {days} "
                   f"day{'s' if days != 1 else ''}. It settles after a few days with the device reader on.",
                   "analytics")]


def _peak_now(snap):
    tariff = snap["tariff"]
    now = tariff.get("now") or {}
    if tariff.get("tariff") != "pop" or not now.get("peak"):
        return []
    until = f" until {now['changes_at']}" if now.get("changes_at") else ""
    return [_alert("peak-now", "info", "It's peak hours on your tariff",
                   f"Electricity costs ₱{tariff['peak_rate']:,.2f} per kWh{until}, then ₱{tariff['offpeak_rate']:,.2f}. "
                   f"Heavy AI jobs are cheaper after that.", "dashboard")]


def build_alerts(snap, own_model=None):
    """Alerts for a snapshot (outlook.snapshot), most urgent first. own_model: the assistant's
    own row in the live reading ("Ollama · <model>")."""
    found = (_budget(snap) + _carbon_budget(snap) + _tips(snap) + _live(snap, own_model)
             + _peak_now(snap) + _coverage(snap))
    return sorted(found, key=lambda a: LEVELS.index(a["level"]))
