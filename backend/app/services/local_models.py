"""Which local models Ollama and LM Studio have loaded or installed, from their own APIs.

Ollama runs each loaded model in its own `ollama runner --model <blob>` process, so a
model's CPU and GPU use is that process's. The blob is matched to the model's name via
the manifests next to it. Older Ollama versions run models inside the server process;
then the model used most recently (latest expiry in /api/ps) gets the server's use.

LM Studio's REST API (or `lms ps`) lists loaded models; when several are loaded, the
app's use is split between them by size.

Every reader returns [] or {} when the app isn't running, so nothing here is required.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime

from .models_catalog import parse_params_b

MODEL_LAYER = "application/vnd.ollama.image.model"
CACHE_S = 60      # manifests and installed models change rarely
LMS_CACHE_S = 10  # `lms ps` starts a process, so don't run it every sample


def ollama_url():
    host = os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434"
    host = host.replace("0.0.0.0", "127.0.0.1")
    return host if host.startswith("http") else f"http://{host}"


def _get_json(url, timeout=0.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:
            return json.load(res)
    except (OSError, ValueError):
        return None


def _parse_time(text):
    """Ollama's RFC 3339 times have up to 9 fractional digits; Python 3.10 reads at most 6."""
    if not text:
        return None
    text = re.sub(r"(\.\d{6})\d+", r"\1", text.replace("Z", "+00:00"))
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


# --- Ollama -----------------------------------------------------------------

def ollama_loaded_models():
    """[{name, size, size_vram, expires_at}] for the models Ollama has in memory."""
    data = _get_json(f"{ollama_url()}/api/ps") or {}
    return [{"name": m.get("name") or m.get("model"), "size": m.get("size") or 0,
             "size_vram": m.get("size_vram") or 0, "expires_at": _parse_time(m.get("expires_at"))}
            for m in data.get("models") or [] if m.get("name") or m.get("model")]


def manifest_name(rel_parts):
    """Model name from a manifest's path under manifests/: host/namespace/model/tag."""
    if len(rel_parts) < 4:
        return None
    host, namespace, model, tag = rel_parts[-4:]
    if host == "registry.ollama.ai":
        return f"{model}:{tag}" if namespace == "library" else f"{namespace}/{model}:{tag}"
    return f"{host}/{namespace}/{model}:{tag}"


_blob_cache = {}  # models dir -> (time, {blob file name: [model names]})


def ollama_blob_names(models_dir):
    """{blob file name ("sha256-…"): [model names]} from the manifests in `models_dir`."""
    hit = _blob_cache.get(models_dir)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        return hit[1]
    manifests = os.path.join(models_dir, "manifests")
    out = {}
    for path in glob.glob(os.path.join(manifests, "**", "*"), recursive=True):
        if not os.path.isfile(path):
            continue
        name = manifest_name(os.path.relpath(path, manifests).replace("\\", "/").split("/"))
        try:
            with open(path, encoding="utf-8") as f:
                layers = json.load(f).get("layers") or []
        except (OSError, ValueError, AttributeError):
            continue
        for layer in layers:
            if name and layer.get("mediaType") == MODEL_LAYER and layer.get("digest"):
                out.setdefault(layer["digest"].replace(":", "-"), []).append(name)
    _blob_cache[models_dir] = (time.monotonic(), out)
    return out


def ollama_model_for_blob(model_path, loaded_names=()):
    """The name of the model whose weights are at `model_path`, preferring one that's loaded."""
    blob = os.path.basename(model_path)
    models_dir = os.path.dirname(os.path.dirname(model_path))  # …/models/blobs/sha256-…
    names = ollama_blob_names(models_dir).get(blob, [])
    loaded = [n for n in names if n in loaded_names]
    return (loaded or sorted(names) or [None])[0]


def _memory_split(loaded_model):
    """How much of a loaded model sits in GPU memory (VRAM), from /api/ps. On Apple Silicon
    the GPU shares system memory, and Ollama counts a model running on it as all VRAM."""
    mib = 1_048_576
    return {"vram_mb": round(loaded_model["size_vram"] / mib, 1), "model_mb": round(loaded_model["size"] / mib, 1)}


def _label_ollama(rows):
    if not rows:
        return []
    loaded = ollama_loaded_models()
    by_name = {m["name"]: m for m in loaded}
    runners = [r for r in rows if r.get("model_path")]
    if runners:
        for r in runners:
            name = ollama_model_for_blob(r["model_path"], by_name)
            if not name and len(loaded) == 1 and len(runners) == 1:
                name = loaded[0]["name"]
            r["model"] = f"Ollama · {name or 'unknown model'}"
            if name in by_name:
                r.update(_memory_split(by_name[name]))
        return rows  # the server process keeps the plain "Ollama" row
    if not loaded:
        return rows
    # Models run inside the server: its use goes to the most recently used model, and
    # the other loaded models get rows with no CPU, so the time they sit idle is recorded.
    active = max(loaded, key=lambda m: m["expires_at"] or 0)
    total = sum(m["size"] for m in loaded) or len(loaded)
    out = []
    for row in rows:
        if row.get("model") or row["app"] != "Ollama":
            out.append(row)
            continue
        for m in loaded:
            share = (m["size"] or 1) / total
            out.append({**row, "model": f"Ollama · {m['name']}", "pids": row.get("pids", []) if m is active else [],
                        "cpu_percent": row["cpu_percent"] if m is active else 0.0,
                        "rss_mb": row["rss_mb"] * share, **_memory_split(m)})
    return out


def ollama_installed_models():
    data = _get_json(f"{ollama_url()}/api/tags") or {}
    out = []
    for m in data.get("models") or []:
        details = m.get("details") or {}
        name = m.get("name") or m.get("model")
        if name:
            out.append({"app": "Ollama", "name": name, "family": details.get("family"),
                        "params_b": parse_params_b(details.get("parameter_size") or name),
                        "quantization": details.get("quantization_level"), "size_bytes": m.get("size")})
    return out


# --- LM Studio --------------------------------------------------------------

LMSTUDIO_URL = "http://127.0.0.1:1234/api/v0/models"
_lms_cache = {"at": 0.0, "models": []}


def _lms_binary():
    for path in (shutil.which("lms"), os.path.expanduser("~/.lmstudio/bin/lms"),
                 os.path.expanduser("~/.cache/lm-studio/bin/lms")):
        if path and os.path.exists(path):
            return path
    return None


def parse_lms_ps(text):
    """Loaded model names from `lms ps --json` output (a list of models)."""
    try:
        data = json.loads(text or "[]")
    except ValueError:
        return []
    items = data if isinstance(data, list) else data.get("models") or []
    out = []
    for m in items:
        if isinstance(m, dict):
            name = m.get("identifier") or m.get("modelKey") or m.get("path")
            if name:
                out.append({"name": name, "size": m.get("sizeBytes") or 0})
    return out


def lmstudio_models():
    """Every model LM Studio knows, from its REST API (needs its server on), with state and quantization."""
    data = _get_json(LMSTUDIO_URL) or {}
    return [m for m in data.get("data") or [] if m.get("type") in (None, "llm", "vlm")]


def lmstudio_loaded_models():
    now = time.monotonic()
    if now - _lms_cache["at"] < LMS_CACHE_S:
        return _lms_cache["models"]
    models = [{"name": m["id"], "size": 0} for m in lmstudio_models() if m.get("state") == "loaded"]
    if not models:
        lms = _lms_binary()
        if lms:
            try:
                out = subprocess.run([lms, "ps", "--json"], capture_output=True, text=True, timeout=5)
                models = parse_lms_ps(out.stdout) if out.returncode == 0 else []
            except (subprocess.SubprocessError, OSError):
                models = []
    _lms_cache.update(at=now, models=models)
    return models


def _label_lmstudio(rows):
    if not rows:
        return []
    loaded = lmstudio_loaded_models()
    if not loaded:
        return rows
    total = sum(m["size"] for m in loaded) or len(loaded)
    out = []
    for row in rows:
        if row.get("model"):
            out.append(row)
            continue
        for m in loaded:
            share = (m["size"] or 1) / total
            out.append({**row, "model": f"LM Studio · {m['name']}",
                        "cpu_percent": row["cpu_percent"] * share, "rss_mb": row["rss_mb"] * share})
    return out


def lmstudio_installed_models():
    return [{"app": "LM Studio", "name": m["id"], "family": m.get("arch"), "params_b": parse_params_b(m["id"]),
             "quantization": m.get("quantization"), "size_bytes": None} for m in lmstudio_models()]


# --- Both -------------------------------------------------------------------

def label_local_models(apps):
    """Replace each local runner's row with one row per model it has loaded."""
    ollama = [a for a in apps if a["app"] == "Ollama"]
    lmstudio = [a for a in apps if a["app"] == "LM Studio"]
    rest = [a for a in apps if a["app"] not in ("Ollama", "LM Studio")]
    return rest + _label_ollama(ollama) + _label_lmstudio(lmstudio)


_installed = {"at": 0.0, "models": []}


def installed_local_models():
    """Local models on this device (Ollama, LM Studio), for recommendations: size, family, quantization."""
    now = time.monotonic()
    if now - _installed["at"] >= CACHE_S:
        _installed.update(at=now, models=ollama_installed_models() + lmstudio_installed_models())
    return _installed["models"]
