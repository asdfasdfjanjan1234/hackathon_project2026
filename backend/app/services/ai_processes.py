"""Finds running AI apps and local model runners, with their CPU and memory use.

kind "local":  the model runs on this machine, so inference energy is on the user's bill.
kind "client": a cloud AI app; only its own CPU use on this machine is on the bill.
"""

import json
import urllib.request

import psutil

# Checked in order; the first match wins. Arguments are lowercased.
AI_APPS = [
    ("Ollama", "local", lambda name, exe, cmd: name.startswith("ollama")),
    ("LM Studio", "local", lambda name, exe, cmd: "/lm studio.app/" in exe or name in ("lms", "llmster")),
    ("llama.cpp", "local", lambda name, exe, cmd: name in ("llama-server", "llama-cli")),
    ("MLX", "local", lambda name, exe, cmd: "mlx_lm" in cmd),
    ("Claude Desktop", "client", lambda name, exe, cmd: "/claude.app/" in exe),
    ("Claude Code", "client", lambda name, exe, cmd: name == "claude" or "@anthropic-ai/claude-code" in cmd),
    ("ChatGPT", "client", lambda name, exe, cmd: "/chatgpt.app/" in exe),
    ("Cursor", "client", lambda name, exe, cmd: "/cursor.app/" in exe),
    ("OpenCode", "client", lambda name, exe, cmd: "/opencode.app/" in exe or name == "opencode"),
    ("GitHub Copilot", "client", lambda name, exe, cmd: "copilot" in exe),
]


def classify(name, exe, cmdline):
    name, exe, cmd = (name or "").lower(), (exe or "").lower(), (cmdline or "").lower()
    for label, kind, match in AI_APPS:
        if match(name, exe, cmd):
            return label, kind
    return None


def find_ai_processes():
    """CPU % (of one core, like Activity Monitor) and memory per AI app, summed over its processes.

    psutil caches processes between calls, so CPU % is measured since the previous call.
    """
    apps = {}
    for p in psutil.process_iter(["name", "exe", "cmdline", "memory_info"]):
        try:
            cmdline = " ".join(p.info["cmdline"] or [])
            match = classify(p.info["name"], p.info["exe"], cmdline)
            if not match:
                continue
            cpu = p.cpu_percent(None)
            rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        label, kind = match
        app = apps.setdefault(label, {"app": label, "model": None, "kind": kind, "cpu_percent": 0.0, "rss_mb": 0.0})
        app["cpu_percent"] += cpu
        app["rss_mb"] += rss / 1_048_576
    return list(apps.values())


def ollama_loaded_models(timeout=0.5):
    """Models Ollama currently has in memory, as [(name, size_vram_bytes)]."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=timeout) as res:
            data = json.load(res)
    except (OSError, ValueError):
        return []
    return [(m["name"], m.get("size_vram") or m.get("size") or 1) for m in data.get("models", [])]


def split_ollama_by_model(apps):
    """Replace the single Ollama row with one row per loaded model, split by memory size."""
    out = []
    for app in apps:
        models = ollama_loaded_models() if app["app"] == "Ollama" else []
        if not models:
            out.append(app)
            continue
        total = sum(size for _, size in models)
        for name, size in models:
            share = size / total
            out.append({**app, "model": f"Ollama · {name}",
                        "cpu_percent": app["cpu_percent"] * share, "rss_mb": app["rss_mb"] * share})
    return out
