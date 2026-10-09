"""Rule-based recommendations: STOP, SWITCH or REDUCE, each with its expected savings.

Every rule works from what was measured or read on this device:

  budget      the forecast goes over budget: when, and how much the top consumer must drop
  smaller     a big local model, when a smaller one of its family is installed (or known)
  idle        a local model stayed loaded without generating
  quantized   a local model runs at 8 or 16 bits per weight; a 4-bit build needs much less energy per token
  cloud       local AI costs a noticeable amount, and cloud AI would barely touch the bill
  per hour    the local model that costs clearly the most per hour of use
  tool runs   an agent's commands (tests, builds) used more energy than the agent itself
  big cloud   most cloud tokens go to a large model (data-center energy, not on the bill)
  clean hours AI use runs in hours the grid is dirtier than its cleanest window (CO2, not on the bill)
  cheap hours on a peak/off-peak tariff, AI use runs in peak hours (same kWh, lower price)
  growing     usage growing fastest, for a model no other rule covers

monthly_savings is in pesos on this bill. "alternative" recommendations are another way
to save the same energy, so they're left out of the "with recommendations" forecast.
Data-center savings (wh_saved) are never on the bill.
"""

from datetime import date
from math import prod

from .cheap_hours import cheap_hours_rec
from .clean_hours import clean_hours_rec
from .models_catalog import LOCAL_MODELS, RECOMMENDED_QUANT, local_name, model_bytes, quant_bits

MOVABLE_SHARE = 0.5     # assumed share of a model's use that suits a smaller model, or can stop
SMALLER_MAX_RATIO = 0.6 # a "smaller" model must be at most this share of the big one's size
GENERIC_SMALL_B = 8     # suggest a ~8B model when no smaller one is installed
GENERIC_MIN_B = 20      # ... for models at least this big
HIGH_BITS = 6.0         # quantizations above this many bits per weight get the quantized rule
CLOUD_MIN_SHARE = 0.05  # local AI above this share of the baseline bill gets the cloud alternative
PER_HOUR_LEAD = 1.25    # the costliest model per hour must be this much above the next one
MIN_ACTIVE_HOURS = 0.5  # hours of use before a model's cost per hour is trusted
MIN_IDLE_HOURS = 1.0
TOOL_RUN_DAYS = 7


def _peso(x):
    if x < 0.01:
        return "under ₱0.01"
    return f"₱{x:,.0f}" if x >= 10 else f"₱{x:,.2f}"


def _energy(kwh):
    return f"{kwh:,.1f} kWh" if kwh >= 1 else f"{kwh * 1000:,.1f} Wh"


def _date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def _rec(action, rule, model, message, monthly_savings, **extra):
    return {"action": action, "rule": rule, "model": model, "message": message,
            "monthly_savings": round(max(monthly_savings, 0.0), 2), "scope": "bill", "alternative": False, **extra}


def _model_info(model, installed):
    """What's known about a local model: from this device's runtimes, else the catalog."""
    name = local_name(model)
    for info in installed:
        if info["name"] == name:
            return info
    return {"name": name, **LOCAL_MODELS.get(name, {})}


def _budget(forecast, budget, today, saved):
    """Runs after the other rules: says whether they keep the bill under budget, and if not,
    how much more the biggest remaining consumer has to drop for the rest of the cycle."""
    over = forecast["forecast_bill"] - budget
    if over <= 0 or not forecast["by_model"]:
        return []
    when = forecast.get("budget_exceeded_on")
    passed = when and date.fromisoformat(when) <= today
    lead = (f"You passed your {_peso(budget)} budget on {_date(when)}" if passed else
            f"At this rate you'll pass your {_peso(budget)} budget on {_date(when)}" if when else
            f"Your forecast is over your {_peso(budget)} budget")
    # What's left of each model's cost for the rest of the cycle once the other recommendations apply.
    left = {m["model"]: (m.get("remaining_cost") or 0.0) * (1 - saved.get(m["model"], 0.0))
            for m in forecast["by_model"]}
    with_recs = forecast["forecast_bill"] - sum((m.get("remaining_cost") or 0.0) * saved.get(m["model"], 0.0)
                                                for m in forecast["by_model"])
    if with_recs <= budget:
        return [_rec("REDUCE", "budget", forecast["by_model"][0]["model"],
                     f"{lead} and end {_peso(over)} over. The recommendations below bring this cycle to "
                     f"{_peso(with_recs)}, under your budget.", 0.0)]
    still = with_recs - budget
    top = max(forecast["by_model"], key=lambda m: left[m["model"]])
    after = "" if with_recs == forecast["forecast_bill"] else f" Even with the recommendations below it's {_peso(still)} over."
    if left[top["model"]] >= still:
        cut = still / left[top["model"]]
        monthly = cut * top["monthly_cost"] * (1 - saved.get(top["model"], 0.0))
        return [_rec("REDUCE", "budget", top["model"],
                     f"{lead} and end {_peso(over)} over.{after} Cut {top['model']} use by {cut:.0%} for the "
                     f"rest of the cycle to stay under it.", monthly, budget_cut=round(cut, 3))]
    if sum(left.values()) >= still:
        cut = still / sum(left.values())
        return [_rec("REDUCE", "budget", top["model"],
                     f"{lead} and end {_peso(over)} over.{after} Cut all AI use by {cut:.0%} for the rest of the "
                     f"cycle (most of it is {top['model']}) to stay under it.",
                     cut * sum(m["monthly_cost"] * (1 - saved.get(m["model"], 0.0)) for m in forecast["by_model"]),
                     budget_cut=round(cut, 3), applies_to=list(left))]
    return [_rec("REDUCE", "budget", top["model"],
                 f"{lead} and end {_peso(over)} over.{after} Cutting AI use alone can't fix it this cycle: most "
                 f"of the bill is non-AI use, like aircon and appliances.", 0.0)]


def _smaller(m, installed):
    info = _model_info(m["model"], installed)
    size = model_bytes(info)
    name = info["name"]
    alt, ratio = None, None
    if size:
        family = [i for i in installed if i["name"] != name and i.get("family") == info.get("family")
                  and model_bytes(i) and model_bytes(i) <= size * SMALLER_MAX_RATIO]
        if family:
            best = max(family, key=model_bytes)
            alt, ratio = best["name"], model_bytes(best) / size
    if not alt and LOCAL_MODELS.get(name, {}).get("smaller_alternative"):
        alt = LOCAL_MODELS[name]["smaller_alternative"]
        alt_size = model_bytes(LOCAL_MODELS[alt]) if size else None
        ratio = alt_size / size if alt_size else LOCAL_MODELS[alt]["avg_watts"] / LOCAL_MODELS[name]["avg_watts"]
    if not alt and (info.get("params_b") or 0) >= GENERIC_MIN_B:
        alt, ratio = f"a {GENERIC_SMALL_B}B model of the same family", GENERIC_SMALL_B / info["params_b"]
    if not alt or not ratio or ratio >= 1:
        return []
    savings = m["monthly_cost"] * MOVABLE_SHARE * (1 - ratio)
    return [_rec("SWITCH", "smaller", m["model"],
                 f"{name} needs about {1 / ratio:.1f}× the energy per token of {alt} (estimated from model size). "
                 f"Use {alt} for simple tasks: moving half of its use saves about {_peso(savings)} a month.",
                 savings, alternative_model=alt)]


def _quantized(m, installed):
    info = _model_info(m["model"], installed)
    bits = quant_bits(info.get("quantization"))
    target = quant_bits(RECOMMENDED_QUANT)
    if not bits or bits <= HIGH_BITS:
        return []
    ratio = target / bits
    savings = m["monthly_cost"] * (1 - ratio)
    return [_rec("SWITCH", "quantized", m["model"],
                 f"{info['name']} runs at {info['quantization']} ({bits:g} bits per weight). The {RECOMMENDED_QUANT} "
                 f"build needs about {1 - ratio:.0%} less energy per token with nearly the same quality, "
                 f"saving about {_peso(savings)} a month.", savings)]


def _idle(idle_loaded, by_model, rate):
    recs = []
    for i in idle_loaded:
        if i["idle_hours"] < MIN_IDLE_HOURS or i["model"] not in by_model:
            continue
        monthly = i["kwh"] * rate * 30 / i["days"]
        name = local_name(i["model"])
        how = ("set OLLAMA_KEEP_ALIVE=10m or run `ollama stop`" if i["model"].startswith("Ollama") or name in LOCAL_MODELS
               else "eject it, or turn on auto-unload")
        recs.append(_rec("REDUCE", "idle", i["model"],
                         f"{name} stayed loaded for {i['idle_hours']:,.0f} idle hours in the last {i['days']} days, "
                         f"holding {i['rss_mb'] / 1024:,.1f} GB of memory and using {_energy(i['kwh'])} "
                         f"(about {_peso(monthly)} a month). Unload it after use: {how}.", monthly))
    return recs


def _cloud_alternative(forecast):
    local = [m for m in forecast["by_model"] if m["kind"] == "local"]
    cost = sum(m["monthly_cost"] for m in local)
    if not local or cost < CLOUD_MIN_SHARE * forecast["baseline_bill"]:
        return []
    savings = cost * MOVABLE_SHARE
    return [_rec("SWITCH", "cloud", local[0]["model"],
                 f"Local AI adds about {_peso(cost)} to this month's bill. A cloud model's energy is used in the "
                 f"provider's data center, so moving half of these tasks to one saves about {_peso(savings)} a month "
                 f"on your bill (it still uses energy, just not yours).", savings, alternative=True)]


def _per_hour(daily, rate, covered):
    totals = {}
    for r in daily:
        if r.get("kind") == "local" and r.get("source", "measured") == "measured":
            t = totals.setdefault(r["model"], [0.0, 0.0])
            t[0] += r["kwh"]
            t[1] += r.get("active_hours") or 0.0
    costs = sorted(((kwh / hours * rate, model) for model, (kwh, hours) in totals.items()
                    if hours >= MIN_ACTIVE_HOURS), reverse=True)
    if len(costs) < 2 or costs[0][0] < PER_HOUR_LEAD * costs[1][0] or costs[0][1] in covered:
        return None
    return costs[0], costs[1]


def _tool_runs(daily, by_model, rate, today):
    recs = []
    recent = [r for r in daily if (today - date.fromisoformat(str(r["date"])[:10])).days < TOOL_RUN_DAYS]
    for model in {r["model"] for r in recent if r["model"].endswith(" · tool runs")}:
        agent = model.split(" · ")[0]
        tool = sum(r["kwh"] for r in recent if r["model"] == model)
        own = sum(r["kwh"] for r in recent if r["model"] != model and r["model"].split(" · ")[0] == agent)
        if tool <= 0 or tool < own:
            continue
        savings = (by_model[model]["monthly_cost"] if model in by_model else tool * rate * 30 / TOOL_RUN_DAYS) * 0.5
        recs.append(_rec("REDUCE", "tool runs", model,
                         f"{agent}'s tool runs (tests, builds and commands it ran) used {_energy(tool)} this week "
                         f"({_peso(tool * rate)}), more than {agent} itself ({_energy(own)}). Ask it to run only "
                         f"the affected tests instead of the whole suite.", savings))
    return recs


def build_recommendations(daily, forecast, rate, budget, signals=None, today=None):
    signals = signals or {}
    today = today or date.today()
    installed = signals.get("installed") or []
    by_model = {m["model"]: m for m in forecast["by_model"]}
    local = [m for m in forecast["by_model"] if m["kind"] == "local" and m["monthly_cost"] > 0]

    recs = []
    for m in local:
        recs += _smaller(m, installed) + _quantized(m, installed)
    recs += _idle(signals.get("idle_loaded") or [], by_model, rate)
    recs += _cloud_alternative(forecast)
    recs += _tool_runs(daily, by_model, rate, today)

    covered = {r["model"] for r in recs if r["rule"] in ("smaller", "quantized")}
    worst = _per_hour(daily, rate, covered)
    if worst:
        (cost, model), (next_cost, next_model) = worst
        savings = by_model.get(model, {}).get("monthly_cost", 0.0) * MOVABLE_SHARE
        recs.append(_rec("STOP", "per hour", model,
                         f"{local_name(model)} costs {_peso(cost)} per hour of use, the most of your models "
                         f"({local_name(next_model)}: {_peso(next_cost)}). Stop using it for jobs another model "
                         f"can do.", savings))

    # Growing fastest: only for a model nothing above already covers.
    taken = {r["model"] for r in recs}
    growing = [m for m in forecast["by_model"] if m["daily_trend_kwh"] > 0 and m["monthly_cost"] > 0
               and m["model"] not in taken]
    if growing:
        fastest = max(growing, key=lambda m: m["daily_trend_kwh"])
        recs.append(_rec("STOP", "growing", fastest["model"],
                         f"{fastest['model']} usage is growing fastest (+{_energy(fastest['daily_trend_kwh'])} "
                         f"more each day). Stop using it for non-essential jobs, like overnight batches.",
                         fastest["monthly_cost"] * MOVABLE_SHARE))

    hint = signals.get("cloud")
    if hint:
        recs.append(_rec("SWITCH", "big cloud", ", ".join(hint["models"]), hint["message"], 0.0,
                         scope="datacenter", wh_saved=hint["wh_saved"]))

    for shift in (clean_hours_rec(signals.get("clean_hours")), cheap_hours_rec(signals.get("cheap_hours"))):
        if shift:
            recs.append(shift)

    recs += _budget(forecast, budget, today, reductions(recs, forecast))
    return sorted(recs, key=lambda r: (r["rule"] != "budget", r["scope"] != "bill", r["alternative"],
                                       -r["monthly_savings"]))


def reductions(recs, forecast):
    """{model: share of its energy the recommendations save}. Recommendations on the same model
    compound (each saves its share of what the others leave), and alternatives aren't counted."""
    cost = {m["model"]: m["monthly_cost"] for m in forecast["by_model"]}
    shares = {}
    for r in recs:
        if r["scope"] != "bill" or r["alternative"]:
            continue
        if "budget_cut" in r:  # a cut of what the other recommendations leave
            for model in r.get("applies_to") or [r["model"]]:
                shares.setdefault(model, []).append(r["budget_cut"])
        elif cost.get(r["model"]):
            shares.setdefault(r["model"], []).append(min(r["monthly_savings"] / cost[r["model"]], 1.0))
    return {model: 1 - prod(1 - s for s in parts) for model, parts in shares.items()}
