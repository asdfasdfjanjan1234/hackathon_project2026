import json
import threading
import time
from datetime import datetime

from flask import Response, current_app, jsonify, request, stream_with_context

from ..services import assistant
from ..services.alerts import build_alerts
from ..services.outlook import snapshot
from ..services.usage_store import get_daily_usage
from . import api_bp, bill_params

# The same facts for this long, so a follow-up question sends Ollama the same prompt and it
# reuses what it already read (the reply starts in about a second instead of five).
FACTS_TTL_S = 60
_facts = {}  # key -> (time, snapshot, alerts, now)


def _model():
    return current_app.config["ASSISTANT_MODEL"]


def _snapshot(params, window_id, model):
    key = json.dumps([params, window_id, model], sort_keys=True)
    hit = _facts.get(key)
    if hit and time.monotonic() - hit[0] < FACTS_TTL_S:
        return hit[1:]
    snap = snapshot(params, window_id)
    entry = (time.monotonic(), snap, build_alerts(snap, assistant.own_label(model)), datetime.now())
    _facts.clear()
    _facts[key] = entry
    return entry[1:]


def _ndjson(events):
    """Events as they happen, one JSON object per line."""
    lines = (json.dumps(e, ensure_ascii=False) + "\n" for e in events)
    return Response(stream_with_context(lines), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api_bp.get("/assistant/status")
def assistant_status():
    """Whether the assistant can answer (Ollama running, model downloaded), and the energy its
    own replies used on this computer in the last 30 days."""
    model = _model()
    own = assistant.own_label(model)
    kwh = sum(r["kwh"] for r in get_daily_usage() if r["model"] == own)
    return jsonify({**assistant.status(model),
                    "energy": {"kwh_30d": round(kwh, 6), "cost_30d": round(kwh * bill_params()["rate"], 4)}})


@api_bp.post("/assistant/chat")
def assistant_chat():
    """A reply about the dashboard's numbers, streamed as NDJSON events (assistant.stream_reply).

    Body: {messages: [{role, content}], view, range, brief: [alert ids]}. With `brief`, the
    assistant talks the user through those alerts instead of answering a question.
    """
    body = request.get_json(silent=True) or {}
    model = _model()
    ready = assistant.status(model)
    if ready["state"] != "ready":
        return jsonify({"error": ready["hint"], "state": ready["state"]}), 503
    snap, alerts, now = _snapshot(bill_params(), body.get("range", "30d"), model)
    messages = assistant.build_messages(snap, alerts, model, body.get("messages"), body.get("view"),
                                        body.get("brief"), now)
    if not messages:
        return jsonify({"error": "Nothing to answer: send a question, or alerts that are still showing."}), 409
    return _ndjson(assistant.stream_reply(model, messages, current_app.config["ASSISTANT_KEEP_ALIVE"]))


@api_bp.post("/assistant/warm")
def assistant_warm():
    """Have Ollama load the model and read the current facts while the user is still typing,
    so the first reply starts in about a second. Body: {view, range}. Returns at once."""
    body = request.get_json(silent=True) or {}
    model = _model()
    if assistant.status(model)["state"] != "ready":
        return jsonify({"warming": False})
    snap, alerts, now = _snapshot(bill_params(), body.get("range", "30d"), model)
    messages = assistant.build_messages(snap, alerts, model, [{"role": "user", "content": "Hi"}], body.get("view"),
                                        now=now)
    threading.Thread(target=assistant.warm, args=(model, messages, current_app.config["ASSISTANT_KEEP_ALIVE"]),
                     daemon=True).start()
    return jsonify({"warming": True})


@api_bp.post("/assistant/pull")
def assistant_pull():
    """Download the assistant's model through Ollama, streaming its progress."""
    return _ndjson(assistant.pull(_model()))
