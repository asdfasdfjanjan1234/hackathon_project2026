"""Applies recommendations to local models through Ollama's API, so a saving can be seen live.

  unload   the model leaves memory now (keep_alive 0): idle-loaded models, and STOP advice
  switch   unload the big model and load the smaller one in its place

The app can't change which model another tool asks for, so a switch is recorded in SWITCHES:
a tool that reads GET /api/actions/state (like demo_load.py) follows it. Other tools need the
model changed in their own settings.

Only models Ollama has loaded right now can be acted on; everything else returns None.
"""

import json
import threading
import urllib.request

from .local_models import ollama_installed_models, ollama_loaded_models, ollama_url
from .models_catalog import local_name

UNLOAD_RULES = {"idle", "per hour", "growing"}
LOAD_TIMEOUT_S = 300  # loading a big model from disk can take minutes

SWITCHES = {}  # {big model: smaller model}, for this run of the backend


def _post(path, body, timeout):
    req = urllib.request.Request(f"{ollama_url()}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def unload(model):
    _post("/api/generate", {"model": model, "keep_alive": 0}, timeout=30)


def load_in_background(model):
    """Load `model` without blocking the request; Ollama keeps it for its default keep-alive."""
    def run():
        try:
            _post("/api/generate", {"model": model}, timeout=LOAD_TIMEOUT_S)
        except OSError:
            pass
    threading.Thread(target=run, daemon=True).start()


def available(rec, loaded=None, installed=None):
    """What applying `rec` would do, or None if it can't be applied from here."""
    if rec.get("scope") != "bill" or rec.get("alternative"):
        return None
    name = local_name(rec["model"])
    loaded = {m["name"] for m in (ollama_loaded_models() if loaded is None else loaded)}
    if name not in loaded:
        return None
    if rec["rule"] == "smaller":
        alt = rec.get("alternative_model")
        names = {m["name"] for m in (ollama_installed_models() if installed is None else installed)}
        if alt in names:
            return {"kind": "switch", "model": name, "to": alt,
                    "label": f"Unload {name} and load {alt}"}
        return None
    if rec["rule"] in UNLOAD_RULES:
        return {"kind": "unload", "model": name, "label": f"Unload {name} from memory"}
    return None


def annotate(recs):
    """Adds `apply` to each recommendation that can be applied now (reads Ollama once)."""
    loaded = ollama_loaded_models()
    installed = ollama_installed_models() if loaded else []
    for r in recs:
        r["apply"] = available(r, loaded, installed) if loaded else None
    return recs


def apply(action):
    """Carry out an action from available(); returns what was done, in words."""
    if action["kind"] == "switch":
        SWITCHES.pop(action["to"], None)  # an earlier switch away from the new model no longer holds
        SWITCHES[action["model"]] = action["to"]
        unload(action["model"])
        load_in_background(action["to"])
        return f"Unloaded {action['model']}; loading {action['to']} in its place."
    unload(action["model"])
    return f"Unloaded {action['model']} from memory."
