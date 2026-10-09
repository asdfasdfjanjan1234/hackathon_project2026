"""Finds running AI apps and local model runners, with their CPU and memory use.

kind "local":  the model runs on this machine, so inference energy is on the user's bill.
kind "client": a cloud AI app; only its own CPU use on this machine is on the bill.

Processes started by a coding agent (tests, builds, shells) count toward that agent as
"tool runs": they use this machine's CPU, so they are on the bill too. Each app also gets
the host it runs in (VS Code, Terminal, ...), found by walking up its parent processes.

Apps not listed here are found by their network connections: a process talking to an AI
provider's API is counted as an "unrecognized AI app", so new tools show up without a
code change.
"""

import os
import re
import socket
import threading
import time

import psutil


def _is_antigravity(name, exe):
    # macOS app bundle, Windows (%LOCALAPPDATA%/Programs/Antigravity) and Linux (/usr/share/antigravity).
    return "/antigravity.app/" in exe or "/antigravity/" in exe or name == "antigravity.exe"


def _is_kiro(name, exe):
    # macOS app bundle, Windows (%LOCALAPPDATA%/Programs/Kiro) and Linux (/usr/share/kiro).
    return "/kiro.app/" in exe or "/programs/kiro/" in exe or "/share/kiro/" in exe or name == "kiro.exe"


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
    ("Antigravity", "client", lambda name, exe, cmd: _is_antigravity(name, exe)),
    ("Kiro", "client", lambda name, exe, cmd: _is_kiro(name, exe)),
    ("Gemini CLI", "client", lambda name, exe, cmd: name == "gemini" or "@google/gemini-cli" in cmd),
    ("OpenCode", "client", lambda name, exe, cmd: "/opencode.app/" in exe or name == "opencode"),
    # Last: VS Code forks bundle VS Code's Copilot runtime, so they must match first.
    ("GitHub Copilot", "client", lambda name, exe, cmd: "copilot" in exe),
]

# Agents whose child processes are commands they ran for the user. Not IDEs like
# Cursor: their children include the user's own terminals.
TOOL_RUNNERS = {"Claude Code", "Codex", "Gemini CLI", "OpenCode"}

HOSTS = [
    ("VS Code", lambda name, exe: "/visual studio code.app/" in exe or name == "code.exe"),
    ("Cursor", lambda name, exe: "/cursor.app/" in exe or name == "cursor.exe"),
    ("Windsurf", lambda name, exe: "/windsurf.app/" in exe or name == "windsurf.exe"),
    ("Antigravity", lambda name, exe: _is_antigravity(name, exe)),
    ("Kiro", lambda name, exe: _is_kiro(name, exe)),
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


def group_processes(procs, exclude=(), extra=None):
    """Assign processes to AI apps.

    procs: {pid: {"ppid", "name", "exe", "cmdline"}}. Returns {pid: (app, kind, host, is_tool_run)}.
    Processes in `exclude` (and their children) are skipped, so this app never measures itself.
    `extra` = {pid: (app, kind)} for apps found another way (unrecognized_apps).
    """
    extra = extra or {}
    direct = {pid: classify(p["name"], p["exe"], p["cmdline"]) or extra.get(pid) for pid, p in procs.items()}
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


# --- Apps not in AI_APPS --------------------------------------------------------

# AI APIs served from addresses of their own. Most other providers (Google, Mistral,
# OpenRouter, Groq, ...) sit behind CDN addresses shared with unrelated sites, which
# would flag apps that never use AI, so they aren't listed.
AI_API_HOSTS = ("api.anthropic.com", "api.openai.com", "api.githubcopilot.com",
                "api.individual.githubcopilot.com")
DNS_EVERY_S = 600   # re-resolve the APIs this often; addresses seen before are kept
SCAN_EVERY_S = 15   # read every process's connections this often
STICKY_S = 600      # an app stays counted this long after its last API connection
UNRECOGNIZED = "unrecognized AI app"

# Browsers reach AI websites but also everything else, so their use isn't counted as AI.
BROWSERS = {"safari", "google chrome", "chrome", "chromium", "firefox", "microsoft edge", "msedge",
            "brave browser", "brave", "arc", "opera", "vivaldi", "dia", "comet", "chatgpt atlas"}
SYSTEM_DIRS = ("/system/", "/usr/libexec/", "/usr/sbin/", "/sbin/", "c:/windows/")
INTERPRETER = re.compile(r"(python|node|bun|deno|ruby)[\d.]*(\.exe)?$")

_api_ips = {"at": None, "ips": set()}
_scan = {"at": None}
_seen = {}  # app key -> last time it had a connection to an AI API


def _resolve_api_ips():
    ips = set()
    for host in AI_API_HOSTS:
        try:
            ips.update(a[4][0] for a in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP))
        except OSError:
            continue
    _api_ips["ips"] = _api_ips["ips"] | ips  # replaced, not changed, while the sampler may be reading it


def ai_api_ips():
    """Addresses of the AI APIs. Resolved in the background so a slow DNS never stalls sampling."""
    now = time.monotonic()
    if _api_ips["at"] is None or now - _api_ips["at"] >= DNS_EVERY_S:
        _api_ips["at"] = now
        threading.Thread(target=_resolve_api_ips, daemon=True).start()
    return _api_ips["ips"]


def _bundle(exe):
    """The outermost macOS app bundle in a path ("/Applications/Zed.app/…" → "/Applications/Zed.app")."""
    m = re.search(r"^(.*?/([^/]+)\.app)/", exe)
    return (m.group(1), m.group(2)) if m else None


def app_name(name, exe, argv):
    """What to call an unrecognized app: its macOS bundle, the package or script an
    interpreter runs (`python /usr/local/bin/aider` → "aider"), else the process name."""
    if INTERPRETER.match((name or "").lower()):
        script = next((a for a in argv[1:] if not a.startswith("-")), None)
        if script:
            script = script.replace("\\", "/")
            pkg = re.search(r"node_modules/((?:@[^/]+/)?[^/]+)", script)
            return pkg.group(1) if pkg else os.path.splitext(os.path.basename(script))[0]
    bundle = _bundle((exe or "").replace("\\", "/"))
    return bundle[1] if bundle else re.sub(r"\.exe$", "", name or "", flags=re.I)


def app_key(pid, p):
    """Processes with the same key are one app: a whole macOS bundle (its network helper is
    often not the process doing the work), or all copies of one program. Interpreters are
    keyed by process, since every Python script shares the same program (on macOS, even
    the same Python.app bundle)."""
    exe = (p["exe"] or "").replace("\\", "/")
    if INTERPRETER.match((p["name"] or "").lower()) or not exe:
        return (pid, p["name"])
    bundle = _bundle(exe)
    return bundle[0].lower() if bundle else exe.lower()


def is_candidate(pid, procs, known):
    """Could this be an AI app we don't know? Not a known app or a child of one (those are
    tool runs), not a known editor or terminal (their AI extensions share one process with
    everything else), not a browser and not part of the OS. known = {pid: classify(...)}."""
    p = procs[pid]
    name, exe, _ = _norm(p["name"], p["exe"], "")
    if known[pid] or host_of(name, exe) or exe.startswith(SYSTEM_DIRS):
        return False
    if any(known[a] for a in _ancestors(pid, procs)):
        return False
    return app_name(p["name"], p["exe"], []).lower() not in BROWSERS


def unrecognized_apps(procs, talks_to_ai, now=None):
    """{pid: (app name, "client")} for apps not in AI_APPS that recently talked to an AI API.

    talks_to_ai(pid) says whether a process has a connection to one now. It is asked every
    SCAN_EVERY_S, and an app stays counted for STICKY_S after, so the work it does between
    requests is counted too.
    """
    now = time.monotonic() if now is None else now
    for key in [k for k, t in _seen.items() if now - t >= STICKY_S]:
        del _seen[key]
    scan = _scan["at"] is None or now - _scan["at"] >= SCAN_EVERY_S
    if not scan and not _seen:
        return {}
    known = {pid: classify(p["name"], p["exe"], p["cmdline"]) for pid, p in procs.items()}
    candidates = [pid for pid in procs if is_candidate(pid, procs, known)]
    if scan:
        _scan["at"] = now
        for pid in candidates:
            if talks_to_ai(pid):
                _seen[app_key(pid, procs[pid])] = now
    return {pid: (app_name(procs[pid]["name"], procs[pid]["exe"], procs[pid].get("argv") or []), "client")
            for pid in candidates if app_key(pid, procs[pid]) in _seen}


def _connected_to(handle, ips):
    try:
        return any(c.raddr and c.raddr.ip in ips for c in handle.net_connections(kind="inet"))
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
        return False


def flag_value(argv, flag):
    """The value after `flag` in an argument list (`--flag value` or `--flag=value`)."""
    for i, arg in enumerate(argv):
        if arg == flag and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith(flag + "="):
            return arg[len(flag) + 1:]
    return None


def find_ai_processes():
    """CPU % (of one core, like Activity Monitor) and memory per AI app, summed over its processes.

    One row per app and host, plus a "tool runs" row for commands an agent started. Each
    Ollama model runner (`ollama runner --model <blob>`) gets its own row with its model
    path, which local_models.label_local_models turns into the model's name. Rows keep
    their process IDs so per-process GPU readings can be matched to them.
    psutil caches processes between calls, so CPU % is measured since the previous call.
    """
    handles, procs, argv = {}, {}, {}
    for p in psutil.process_iter(["ppid", "name", "exe", "cmdline"]):
        try:
            argv[p.pid] = p.info["cmdline"] or []
            procs[p.pid] = {**p.info, "cmdline": " ".join(argv[p.pid]), "argv": argv[p.pid]}
            handles[p.pid] = p
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    ips = ai_api_ips()
    extra = unrecognized_apps(procs, lambda pid: _connected_to(handles[pid], ips)) if ips else {}
    unknown = {label for label, _ in extra.values()}

    apps = {}
    for pid, (label, kind, host, tool_run) in group_processes(procs, exclude={os.getpid()}, extra=extra).items():
        p = handles[pid]
        try:
            cpu = p.cpu_percent(None)
            rss = p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        model_path = flag_value(argv[pid], "--model") if label == "Ollama" and not tool_run else None
        key = (label, host, tool_run, model_path)
        model = f"{label} · tool runs" if tool_run else f"{label} · {UNRECOGNIZED}" if label in unknown else None
        app = apps.setdefault(key, {"app": label, "model": model,
                                    "kind": kind, "host": host, "cpu_percent": 0.0, "rss_mb": 0.0,
                                    "pids": [], "model_path": model_path})
        app["cpu_percent"] += cpu
        app["rss_mb"] += rss / 1_048_576
        app["pids"].append(pid)
    return list(apps.values())


def label_active_models(apps, active):
    """Name the cloud model each client app is using, from `active` = {app: model id}."""
    for app in apps:
        model = active.get(app["app"])
        if app["kind"] == "client" and app["model"] is None and model:
            app["model"] = f"{app['app']} · {model}"
    return apps
