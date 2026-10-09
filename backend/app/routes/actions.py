from flask import jsonify, request

from ..services import actions
from . import api_bp


@api_bp.post("/actions/apply")
def apply_action():
    """Apply a recommendation (as returned by /api/recommendations) to Ollama, if it still can be."""
    rec = request.get_json(silent=True) or {}
    if not {"rule", "model", "scope"} <= rec.keys():
        return jsonify({"error": "send a recommendation from /api/recommendations"}), 400
    action = actions.available(rec)
    if not action:
        return jsonify({"error": "This can't be applied right now: the model isn't loaded in Ollama."}), 409
    try:
        done = actions.apply(action)
    except OSError as e:
        return jsonify({"error": f"Ollama didn't respond: {e}"}), 502
    return jsonify({"done": done, "action": action, "switches": actions.SWITCHES})


@api_bp.get("/actions/state")
def action_state():
    """Model switches applied in this run: {big model: smaller model}. demo_load.py follows them."""
    return jsonify({"switches": actions.SWITCHES})
