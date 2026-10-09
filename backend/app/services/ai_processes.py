"""Finds running AI apps and local model runners, with their CPU and memory use.

kind "local":  the model runs on this machine, so inference energy is on the user's bill.
kind "client": a cloud AI app; only its own CPU use on this machine is on the bill.

Processes started by a coding agent (tests, builds, shells) count toward that agent as
"tool runs": they use this machine's CPU, so they are on the bill too. Each app also gets
the host it runs in (VS Code, Terminal, ...), found by walking up its parent processes.
"""

import json
import os
import urllib.request

import psutil

# Checked in order; the first match wins. Arguments are lowercased, with "/" as path separator.
AI_APPS = [
    ("Ollama", "local", lambda name, exe, cmd: name.startswith("ollama")),
    ("LM Studio", "local", lambda name, exe, cmd: "/lm studio.app/" in exe or name in ("lms", "llmster")),
    ("llama.cpp", "local", lambda name, exe, cmd: name in ("llama-server", "llama-cli")),
    ("MLX", "local", lambda name, exe, cmd: "mlx_lm" in cmd),
    ("Claude Desktop", "client", lambda name, exe, cmd: "/claude.app/" in exe),
    ("Claude Code", "client", lambda name, exe, cmd: name == "claude" or "@anthropic-ai/claude-code" in cmd),
    ("Codex", "client", lambda name, exe, cmd: name in ("codex", "codex.exe") or "/openai.chatgpt-" in exe),
    ("Amazon Q", "client", lambda name, exe, cmd: "/aws/language-servers/" in exe or "amazonq" in name),
    ("ChatGPT", "client", lambda name, exe, cmd: "/chatgpt.app/" in exe),
    ("Cursor", "client", lambda name, exe, cmd: "/cursor.app/" in exe),
    ("Windsurf", "client", lambda name, exe, cmd: "/windsurf.app/" in exe),
    ("OpenCode", "client", lambda name, exe, cmd: "/opencode.app/" in exe or name == "opencode"),
    ("GitHub Copilot", "client", lambda name, exe, cmd: "copilot" in exe),
]

# Agents whose child processes are commands they ran for the user. Not IDEs like
# Cursor: their children include the user's own terminals.
TOOL_RUNNERS = {"Claude Code", "Codex", "OpenCode"}

HOSTS = [
    ("VS Code", lambda name, exe: "/visual studio code.app/" in exe or name == "code.exe"),
    ("Cursor", lambda name, exe: "/cursor.app/" in exe or name == "cursor.exe"),
    ("Windsurf", lambda name, exe: "/windsurf.app/" in exe or name == "windsurf.exe"),
    ("Terminal", lambda name, exe: "/terminal.app/" in exe),
    ("iTerm", lambda name, exe: "/iterm.app/" in exe),
    ("Warp", lambda name, exe: "/warp.app/" in exe),
    ("Windows Terminal", lambda name, exe: name == "windowsterminal.exe"),
    ("PowerShell", lambda name, exe: name in ("powershell.exe", "pwsh.exe")),
]

MAX_DEPTH = 40  # guards against cycles in the parent chain


def _norm(name, exe, cmdline):
    return (name or "").lower(), (exe or "").lower().replace("\\", "/"), (cmdline or "").lower()


def classify(name, exe, cmdline):
    name, exe, cmd = _norm(name, exe, cmdline)
    for label, kind, match in AI_APPS:
        if match(name, exe, cmd):
            return label, kind
    return None


def host_of(name, exe):
    name, exe, _ = _norm(name, exe, "")
    for label, match in HOSTS:
        if match(name, exe):
            return label
    return None


def _ancestors(pid, procs):
    seen = set()
    pid = procs[pid]["ppid"] if pid in procs else None
    while pid in procs and pid not in seen and len(seen) < MAX_DEPTH:
        seen.add(pid)
        yield pid
        pid = procs[pid]["ppid"]


def group_processes(procs, exclude=()):
    """Assign processes to AI apps.

    procs: {pid: {"ppid", "name", "exe", "cmdline"}}. Returns {pid: (app, kind, host, is_tool_run)}.
    Processes in `exclude` (and their children) are skipped, so this app never measures itself.
    """
    direct = {pid: classify(p["name"], p["exe"], p["cmdline"]) for pid, p in procs.items()}
    out = {}
    for pid, p in procs.items():
        if pid in exclude or any(a in exclude for a in _ancestors(pid, procs)):
            continue
        match, tool_run, root = direct[pid], False, pid
        if not match:
            # A command run by an agent, e.g. `npm test` started by Claude Code.
            agent = next((a for a in _ancestors(pid, procs) if direct[a] and direct[a][0] in TOOL_RUNNERS), None)
            if agent is None:
                continue
            match, tool_run, root = direct[agent], True, agent
        label, kind = match
        host = next((h for a in _ancestors(root, procs)
                     if direct[a] is None or direct[a][0] != label
                     for h in [host_of(procs[a]["name"], procs[a]["exe"])] if h), None)
        out[pid] = (label, kind, host, tool_run)
    return out


def find_ai_processes():
    """CPU % (of one core, like Activity Monitor) and memory per AI app, summed over its processes.

    One row per app and host, plus a "tool runs" row for commands an agent started.
    psutil caches processes between calls, so CPU % is measured since the previous call.
    """
    handles, procs = {}, {}
    for p in psutil.process_iter(["ppid", "name", "exe", "cmdline"]):
        try:
            procs[p.pid] = {**p.info, "cmdline": " ".join(p.info["cmdline"] or [])}
            handles[p.pid] = p
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    apps = {}
    for pid, (label, kind, host, tool_run) in group_processes(procs, exclude={os.getpid()}).items():
        p = handles[pid]
        try:
            cpu = p.cpu_percent(None)
            rss = p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        key = (label, host, tool_run)
        app = apps.setdefault(key, {"app": label, "model": f"{label} · tool runs" if tool_run else None,
                                    "kind": kind, "host": host, "cpu_percent": 0.0, "rss_mb": 0.0})
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


def label_active_models(apps, active):
    """Name the cloud model each client app is using, from `active` = {app: model id}."""
    for app in apps:
        model = active.get(app["app"])
        if app["kind"] == "client" and app["model"] is None and model:
            app["model"] = f"{app['app']} · {model}"
    return apps
