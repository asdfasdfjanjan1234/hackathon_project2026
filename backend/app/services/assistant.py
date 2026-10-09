"""The assistant: a small local model that tells the user what the dashboard's numbers mean.

It runs in Ollama on this computer, so nothing leaves the device, and its own energy use is
measured like any other local model's (its row in the readings is "Ollama · <model>").

The model never does the math. Every figure it may use is worked out by the backend and
handed over as text, already formatted with its unit (facts()), and the prompt tells it to
copy them: small models are good at wording and poor at arithmetic.

  status()        whether Ollama is running and the model is downloaded
  facts()         the dashboard's numbers as text
  build_messages  system prompt + facts + the conversation, or a briefing on alerts
  stream_reply()  the reply from Ollama, piece by piece
  warm()          loads the model and the facts before the question, so the reply starts sooner
  pull()          downloads the model through Ollama
"""

import json
import os
import shutil
import time
import urllib.error
import urllib.request
from datetime import date, datetime

from .local_models import ollama_url

NAME = "Kilo"
TEMPERATURE = 0.3        # low: the job is to restate given figures, not to be inventive
MAX_TOKENS = 320         # a reply is a few sentences
CONTEXT_TOKENS = 8192
MAX_TURNS = 8            # of the conversation sent back to the model
MAX_TURN_CHARS = 2000
MAX_ROWS = 5             # apps or models listed per section
REPLY_TIMEOUT_S = 120    # loading the model from disk comes out of this
PULL_TIMEOUT_S = 60      # between two progress lines, not for the whole download

SYSTEM = """You are {name}, the assistant inside "Kilo What?", an app that measures how much electricity AI tools use on this computer and what that does to the electricity bill and carbon footprint. You run on this same computer.

Your job: tell the user what the numbers mean in plain words, and what to do about them, if anything.

Rules
- Use only the figures in DATA. Copy each number exactly as written, with its unit. Never calculate, round, estimate or invent a number. If DATA doesn't have the answer, say the app doesn't track that.
- Lead with the answer. Two to four short sentences, unless the user asks for detail.
- Write for someone who isn't an engineer. Explain a term the first time you use it.
- Keep things in proportion. A few pesos on a bill of thousands is small: say so plainly instead of raising alarm. If nothing needs doing, say that.
- Plain text only: no markdown, no headings, no lists, no emoji.
- Reply in the language the user writes in (English, Filipino or Taglish).
- You can't change anything yourself. The user applies recommendations in the Load Directives view and changes the rate, bills and budgets in Tariff & Hardware.

Background
- Watts (W) is power being used right now. kWh is energy over time: 1,000 W for one hour. The bill charges per kWh.
- "Measured" is read from the computer's own power sensor. "Estimated" is calculated from CPU and GPU use.
- Local models (Ollama, LM Studio) run on this computer, so all of their energy is on the user's bill.
- Cloud models (Claude, GPT, Gemini) run in the provider's data center. Only the app's own small CPU use here is on the bill. Their data-center energy is estimated from token counts: it is never on the bill, but it still causes CO₂.
- An app's activity: working = generating or running tools. background = open with light upkeep. loaded = a local model held in memory, not generating. idle = open, waiting for a prompt.
- "tool runs" are commands a coding agent ran on this computer (tests, builds).
- CO₂ is the gas that warms the climate; making electricity releases it. It is counted in grams (g) and kilograms (kg), 1 kg = 1,000 g. To make a CO₂ figure feel real, use the comparisons in DATA (car km, phone charges, trees), never your own.
- The carbon budget is a monthly CO₂ cap the user chose. Recommendations (also called directives) cut CO₂ by using less energy, or by running AI in the grid's cleanest hours.
- You run as "{own}". Your own energy use is in the readings too."""

# After DATA: small models follow what they read last.
REMINDER = """Answer in at most 3 short sentences (about 60 words) unless the user asks for detail. Copy figures exactly from DATA. Plain text, no lists."""

BRIEF = """These alerts just came up in the app:
{alerts}

Tell me about them the way a good assistant speaks up: what it means for me, and the one thing worth doing, if any. Most urgent first. Don't repeat yourself. At most {sentences} sentences."""

VIEWS = {
    "dashboard": "Telemetry Console (live power draw, the current bill and where this cycle is heading)",
    "device": "This Device (hardware, power sensors and the AI processes being read)",
    "analytics": "Billing Projection (the projected end-of-cycle bill and how much of it is AI)",
    "models": "Model Runtimes (energy and cost per model)",
    "carbon": "Carbon Ledger (CO₂ from AI on this device and in cloud data centers)",
    "recommendations": "Load Directives (suggested workload changes and what each one saves)",
}


def own_label(model):
    """The assistant's own row in the readings."""
    return f"Ollama · {model}"


# --- Ollama -----------------------------------------------------------------

def _get(path, timeout=1.0):
    try:
        with urllib.request.urlopen(f"{ollama_url()}{path}", timeout=timeout) as res:
            return json.load(res)
    except (OSError, ValueError):
        return None


def _post(path, body, timeout):
    """An open streaming response from Ollama: one JSON object per line."""
    req = urllib.request.Request(f"{ollama_url()}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def _error(e):
    """Ollama explains refused requests ("model not found") in the response body."""
    if isinstance(e, urllib.error.HTTPError):
        try:
            return json.load(e).get("error") or str(e)
        except ValueError:
            return str(e)
    return f"Ollama didn't respond: {e}"


def _ollama_installed():
    paths = ("/Applications/Ollama.app", os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"))
    return bool(shutil.which("ollama")) or any(os.path.exists(p) for p in paths)


def status(model):
    """{state, hint}: "ready", or what's missing ("ollama_missing", "ollama_stopped", "model_missing")."""
    base = {"name": NAME, "model": model, "size_bytes": None}
    tags = _get("/api/tags")
    if tags is None:
        if _ollama_installed():
            return {**base, "state": "ollama_stopped",
                    "hint": "Ollama is installed but not running. Open the Ollama app, or run `ollama serve`."}
        return {**base, "state": "ollama_missing",
                "hint": "The assistant runs on a local model in Ollama. Install it from ollama.com, then come back."}
    found = next((m for m in tags.get("models") or []
                  if (m.get("name") or m.get("model")) in (model, f"{model}:latest")), None)
    if not found:
        return {**base, "state": "model_missing",
                "hint": f"Ollama is running, but {model} isn't downloaded yet."}
    return {**base, "state": "ready", "hint": None, "size_bytes": found.get("size")}


_thinks = {}  # model -> whether it has a thinking mode to turn off


def _can_think(model):
    if model not in _thinks:
        try:
            with _post("/api/show", {"model": model}, timeout=5) as res:
                _thinks[model] = "thinking" in (json.load(res).get("capabilities") or [])
        except (OSError, ValueError):
            return False
    return _thinks[model]


def stream_reply(model, messages, keep_alive="2m", max_tokens=MAX_TOKENS):
    """The reply as events: {type: "delta", text}, then {type: "done", stats} or {type: "error", error}.
    Closing the generator closes the connection, which makes Ollama stop generating."""
    body = {"model": model, "messages": messages, "stream": True, "keep_alive": keep_alive,
            "options": {"temperature": TEMPERATURE, "num_predict": max_tokens, "num_ctx": CONTEXT_TOKENS}}
    if _can_think(model):
        body["think"] = False  # answers come straight away, and cost less energy
    started, first = time.time(), None
    try:
        with _post("/api/chat", body, timeout=REPLY_TIMEOUT_S) as res:
            for line in res:
                chunk = json.loads(line)
                if chunk.get("error"):
                    yield {"type": "error", "error": chunk["error"]}
                    return
                text = (chunk.get("message") or {}).get("content")
                if text:
                    first = first or time.time()
                    yield {"type": "delta", "text": text}
                if chunk.get("done"):
                    yield {"type": "done", "stats": _stats(model, chunk, started, first)}
    except (OSError, ValueError) as e:
        yield {"type": "error", "error": _error(e)}


def warm(model, messages, keep_alive="2m"):
    """Load the model and have it read `messages` (one token of reply), so Ollama has the
    facts ready when the real question comes."""
    for _ in stream_reply(model, messages, keep_alive, max_tokens=1):
        pass


def _stats(model, chunk, started, first):
    seconds = (chunk.get("eval_duration") or 0) / 1e9
    tokens = chunk.get("eval_count") or 0
    return {"model": model, "started": started, "seconds": round(time.time() - started, 2),
            "first_word_seconds": round(first - started, 2) if first else None,
            "load_seconds": round((chunk.get("load_duration") or 0) / 1e9, 2),
            "prompt_tokens": chunk.get("prompt_eval_count") or 0, "tokens": tokens,
            "tokens_per_second": round(tokens / seconds, 1) if seconds else None}


def pull(model):
    """Download `model` through Ollama: {type: "progress", status, completed, total} per step,
    then {type: "done"} or {type: "error", error}."""
    try:
        with _post("/api/pull", {"model": model, "stream": True}, timeout=PULL_TIMEOUT_S) as res:
            for line in res:
                chunk = json.loads(line)
                if chunk.get("error"):
                    yield {"type": "error", "error": chunk["error"]}
                    return
                yield {"type": "progress", "status": chunk.get("status"),
                       "completed": chunk.get("completed"), "total": chunk.get("total")}
        yield {"type": "done"}
    except (OSError, ValueError) as e:
        yield {"type": "error", "error": _error(e)}


# --- Facts ------------------------------------------------------------------

def _peso(x):
    if 0 < abs(x) < 0.01:
        return "under ₱0.01"
    return f"₱{x:,.0f}" if abs(x) >= 10 and float(x).is_integer() else f"₱{x:,.2f}"


def _energy(kwh):
    if kwh >= 1:
        return f"{kwh:,.1f} kWh"
    wh = kwh * 1000
    if 0 < wh < 0.1:
        return "under 0.1 Wh"
    return f"{wh:,.0f} Wh" if wh >= 10 else f"{wh:,.1f} Wh"


def _co2(kg):
    if kg >= 1:
        return f"{kg:,.1f} kg CO₂"
    return "under 1 g CO₂" if 0 < kg < 0.001 else f"{kg * 1000:,.0f} g CO₂"


def _watts(w):
    return f"{w:,.1f} W" if w >= 10 else f"{w:,.2f} W"


def _date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def _where(kind):
    return "local model on this computer" if kind == "local" else "cloud AI app"


def _settings(snap):
    p, tariff = snap["params"], snap["tariff"]
    if tariff["tariff"] == "pop":
        now = tariff["now"]
        until = f" until {now['changes_at']}" if now.get("changes_at") else ""
        rate = (f"Peak/Off-Peak tariff: ₱{tariff['peak_rate']:,.2f} per kWh at peak, ₱{tariff['offpeak_rate']:,.2f} "
                f"off-peak ({tariff['offpeak_label']}). Right now it is {'peak' if now.get('peak') else 'off-peak'}{until}")
    else:
        rate = f"Electricity rate: ₱{p['rate']:,.2f} per kWh, the same at every hour"
    lines = [f"- {rate}", f"- Household bill before AI use: {_peso(p['baseline_bill'])} a month",
             f"- Monthly bill budget: {_peso(p['budget'])}"]
    if p.get("carbon_budget"):
        lines.append(f"- Monthly carbon budget for AI: {p['carbon_budget']:g} kg CO₂")
    return lines


def _bill(snap):
    f = snap["forecast"]
    lines = [f"- Billing cycle: {_date(f['cycle']['start'])} to {_date(f['cycle']['end'])}, {f['days_left']} days left",
             f"- Forecast bill for this cycle: {_peso(f['forecast_bill'])}, which is {_peso(f['baseline_bill'])} "
             f"household bill before AI plus {_peso(f['ai_cost'])} from AI on this computer"]
    over = f["forecast_bill"] - f["budget"]
    if over > 0:
        when = f", passing it on {_date(f['budget_exceeded_on'])}" if f.get("budget_exceeded_on") else ""
        lines.append(f"- Against the {_peso(f['budget'])} budget: OVER by {_peso(over)}{when}")
    else:
        lines.append(f"- Against the {_peso(f['budget'])} budget: under by {_peso(-over)}")
    if f.get("monthly_savings"):
        lines.append(f"- With the recommendations applied: {_peso(f['forecast_bill_with_recommendations'])} this "
                     f"cycle, and {_peso(f['monthly_savings'])} saved in a full month")
    cov = f.get("coverage") or {}
    if cov.get("days_measured"):
        rough = ", so the forecast is still rough" if cov["days_measured"] < 3 else ""
        lines.append(f"- Based on {cov['hours_measured']:,.1f} hours of readings over {cov['days_measured']} "
                     f"day{'s' if cov['days_measured'] != 1 else ''}{rough}")
    else:
        lines.append("- No readings yet, so there is nothing to forecast from")
    year = f["projections"][-1]
    lines.append(f"- The next {year['months']} bills added together (not one month): {_peso(year['bill'])}, of which "
                 f"{_peso(year['ai_cost'])} is AI. The app doesn't forecast further ahead")
    costly = [m for m in f["by_model"] if m["monthly_cost"] > 0][:MAX_ROWS]
    if costly:
        lines.append("- AI cost on the bill per month, biggest first:")
        lines += [f"  - {m['model']} ({_where(m['kind'])}): {_peso(m['monthly_cost'])}, {_energy(m['monthly_kwh'])}"
                  + (", growing" if m["daily_trend_kwh"] > 0 else "") for m in costly]
    return lines


def _usage(snap):
    rows = snap["usage"]
    if not rows:
        return ["- Nothing measured in this window"]
    kwh = sum(r["kwh"] for r in rows)
    local = [r for r in rows if r["kind"] == "local"]
    lines = [f"- All AI apps on this computer: {_energy(kwh)}, costing {_peso(sum(r['cost'] for r in rows))}",
             f"- Local models (all of their energy is on the bill): {_energy(sum(r['kwh'] for r in local))}" if local
             else "- Local models: none used, so all of this is cloud AI apps' own CPU use here",
             "- By app or model, biggest first:"]
    for r in rows[:MAX_ROWS]:
        active = f", {r['active_hours']:,.1f} hours of activity" if r["active_hours"] else ""
        heavy = f", {_watts(r['active_watts'])} while active" if r.get("active_watts") else ""
        lines.append(f"  - {r['model']} ({_where(r['kind'])}): {_energy(r['kwh'])}, {_peso(r['cost'])}{active}{heavy}")
    return lines


def _carbon(snap):
    c = snap["carbon"]
    t, ins = c["totals"], c.get("insights") or {}
    lines = [f"- Total from AI: {_co2(t['total_kg'])}",
             f"- On this computer: {_co2(t['device_kg'])}, from {_energy(t['device_kwh'])} at "
             f"{snap['grid_co2_kg_per_kwh']:g} kg CO₂ per kWh on this grid (the grid factor: how much CO₂ "
             f"the power plants release for each kWh)",
             f"- In cloud data centers: {_co2(t['datacenter_kg'])}, from an estimated {_energy(t['datacenter_kwh'])}. "
             f"Estimated from token counts, and not on the electricity bill"]
    if t["total_kg"]:
        lines.append(f"- Cloud data centers' share of the total: {ins.get('cloud_share', 0):.0%}")
        eq = ins.get("equivalents") or {}
        lines.append(f"- That is about as much CO₂ as driving an average car {eq.get('car_km', 0):,.0f} km, "
                     f"charging a phone {eq.get('phone_charges', 0):,} times on this grid, or what "
                     f"{t['trees_month']:g} trees absorb in a month")
        lines.append(f"- Average day: {_co2(ins.get('avg_per_day_kg', 0))}. AI caused CO₂ on "
                     f"{ins.get('active_days', 0)} of the {len(c['daily'])} days")
    peak = ins.get("peak_day")
    if peak:
        lines.append(f"- Heaviest day: {_date(peak['date'])}, {_co2(peak['kg'])} ({peak['share']:.0%} of the total)")
    trend = ins.get("trend")
    if trend and trend["direction"] != "none":
        word = {"up": "rising", "down": "falling", "flat": "steady"}[trend["direction"]]
        lines.append(f"- Trend: {word}. From {_date(trend['split_date'])} on it averaged "
                     f"{_co2(trend['later_avg_kg'])} a day, against {_co2(trend['earlier_avg_kg'])} a day before")
    if c["by_model"]:
        lines.append("- Biggest sources:")
        for m in c["by_model"][:3]:
            where = "in a data center" if m["scope"] == "datacenter" else "on this computer"
            lines.append(f"  - {m['model']}: {_co2(m['co2_kg'])} ({m['share']:.0%} of the total), {where}")
    cy = c["cycle"]
    heading = f"- This billing cycle is heading for {_co2(cy['projected_kg'])}"
    if cy["projected_kg_with_recommendations"] < cy["projected_kg"]:
        heading += f", or {_co2(cy['projected_kg_with_recommendations'])} with the recommendations"
    b = c.get("budget")
    if b:
        state = {"under": "under it", "fixed_by_recommendations": "OVER it, but under with the recommendations",
                 "over": "OVER it"}[b["status"]]
        heading += f". That is {b['used_share']:.0%} of the {b['kg']:g} kg carbon budget ({state})"
    else:
        heading += ". No carbon budget is set (it is set in Tariff & Hardware)"
    lines.append(heading)
    y = c["year"]
    lines.append(f"- Over 12 months: {y['projected_kg']:,.1f} kg CO₂, or {y['projected_kg_with_recommendations']:,.1f} kg "
                 f"with the recommendations. That avoids {y['avoided_kg']:,.1f} kg, what {y['trees_equivalent']:g} "
                 f"trees absorb in a year")
    if c.get("top_actions"):
        a = c["top_actions"][0]
        lines.append(f"- Biggest CO₂ cut: {a['action']}, {a['model']}, avoids {_co2(a['co2_saved_kg'])} a month")
    return lines


def _best_time(snap):
    tariff, clean = snap["tariff"], snap.get("clean") or {}
    best = tariff.get("best")
    lines = []
    if best and tariff["tariff"] == "flat":
        lines.append(f"- Best window for heavy AI jobs: {best['label']}, when the grid's electricity is cleanest "
                     f"(least CO₂). The rate is the same every hour, so the time of day doesn't change the cost")
    elif best:
        lines.append(f"- Best window for heavy AI jobs: {best['label']}. {best['reason']}")
    if clean.get("now") and clean["now"].get("g_per_kwh") is not None:
        lines.append(f"- The grid right now: {clean['now']['g_per_kwh']:,.0f} g CO₂ per kWh")
    plan = clean.get("plan")
    if plan:
        lines.append(f"- Cleanest hours: {plan['cleanest']['label']} ({plan['cleanest']['g_per_kwh']:,.0f} g). "
                     f"Dirtiest: {plan['dirtiest']['label']} ({plan['dirtiest']['g_per_kwh']:,.0f} g)")
    return lines or ["- No hourly grid data is connected, so there is no best window"]


def _recommendations(snap):
    recs = [r for r in snap["recommendations"] if r["rule"] != "budget"]
    if not recs:
        return ["- None right now"]
    lines = []
    for i, r in enumerate(recs[:MAX_ROWS], 1):
        co2 = f" Avoids {_co2(r['co2_saved_kg'])} a month." if r.get("co2_saved_kg") else ""
        other = " (Another way to save the same energy.)" if r["alternative"] else ""
        lines.append(f"{i}. {r['action']}, {r['model']}: {r['message']}{co2}{other}")
    return lines


def _live(snap, own):
    live = snap["live"]
    how = "estimated from CPU and GPU use" if live.get("estimated") else "measured by the power sensor"
    total = live.get("watts") or 0
    lines = [f"- Whole computer: {total:,.1f} W, {how}"]
    if live.get("source") != "collector":
        return lines + ["- The device reader is off, so there is no reading per AI app. It is started in This Device"]
    apps = live.get("apps") or []
    ai = live.get("ai_watts") or 0
    share = f" ({ai / total:.0%} of the total)" if total else ""
    lines.append(f"- AI apps together: {_watts(ai)}{share}")
    lines.append(f"- The rest of the computer (screen, system, other apps): {_watts(max(total - ai, 0))}")
    if not apps:
        return lines + ["- No AI apps are open"]
    lines.append("- AI apps open, by power:")
    for a in apps[:MAX_ROWS + 1]:
        host = f", in {a['host']}" if a.get("host") else ""
        me = " (this is you)" if a["name"] == own else ""
        lines.append(f"  - {a['name']} ({_where(a['kind'])}{host}): {a['activity']}, {_watts(a['watts'] or 0)}{me}")
    if len(apps) > MAX_ROWS + 1:
        lines.append(f"  - and {len(apps) - MAX_ROWS - 1} more, each using less")
    return lines


def facts(snap, alerts=(), own=None, now=None):
    """The dashboard's numbers as text. Ordered from what changes least to what changes with
    every reading, so Ollama can reuse most of the prompt it already processed."""
    now = now or datetime.now()
    notes = [f"- {a['title']}: {a['text']}" for a in alerts if a["level"] != "tip"]  # tips are the recommendations
    sections = [
        ("SETTINGS (chosen by the user)", _settings(snap)),
        ("BILL FORECAST", _bill(snap)),
        (f"USAGE, {snap['window']['label'].lower()}, measured on this computer", _usage(snap)),
        (f"CARBON, {snap['window']['label'].lower()}", _carbon(snap)),
        ("BEST TIME TO RUN HEAVY AI JOBS", _best_time(snap)),
        ("RECOMMENDATIONS (from the app's rules)", _recommendations(snap)),
        ("ALERTS", notes or ["- None. Nothing needs attention"]),
        (f"RIGHT NOW ({now:%A}, {now:%B} {now.day}, {now.hour % 12 or 12}:{now:%M} {'AM' if now.hour < 12 else 'PM'})",
         _live(snap, own)),
    ]
    return "\n\n".join("\n".join([title, *lines]) for title, lines in sections)


# --- Conversation -----------------------------------------------------------

def _turns(history):
    """The last few turns, cleaned so the roles alternate and a user speaks first."""
    turns = []
    for m in history or []:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        text = str(m.get("content") or "").strip()[:MAX_TURN_CHARS]
        if not text:
            continue
        if turns and turns[-1]["role"] == m["role"]:
            turns[-1]["content"] += "\n\n" + text
        else:
            turns.append({"role": m["role"], "content": text})
    turns = turns[-MAX_TURNS:]
    if turns and turns[0]["role"] == "assistant":  # a briefing the assistant gave unprompted
        turns.insert(0, {"role": "user", "content": "What should I know right now?"})
    return turns


def build_messages(snap, alerts, model, history=None, view=None, brief=None, now=None):
    """Messages for Ollama, or None when there's nothing to answer. brief: ids of the alerts to
    talk the user through, instead of a question from them."""
    own = own_label(model)
    system = f"{SYSTEM.format(name=NAME, own=own)}\n\nDATA\n\n{facts(snap, alerts, own, now)}"
    if view in VIEWS:
        system += f"\n\nThe user is looking at the {VIEWS[view]} view."
    system += f"\n\n{REMINDER}"
    turns = _turns(history)
    if brief is not None:
        chosen = [a for a in alerts if a["id"] in set(brief)]
        if not chosen:
            return None
        listed = "\n".join(f"- {a['title']}: {a['text']}" for a in chosen)
        ask = BRIEF.format(alerts=listed, sentences=min(1 + len(chosen), 4))
        if turns and turns[-1]["role"] == "user":
            turns[-1]["content"] += "\n\n" + ask
        else:
            turns.append({"role": "user", "content": ask})
    if not turns or turns[-1]["role"] != "user":
        return None
    return [{"role": "system", "content": system}, *turns]
