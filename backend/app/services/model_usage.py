"""Which AI models the apps on this device used, read from their local logs.

  Claude Code     ~/.claude/projects/**/*.jsonl                exact tokens per response
  Codex           ~/.codex/sessions/**/rollout-*.jsonl         exact tokens per turn
  OpenCode        ~/.local/share/opencode/opencode.db          exact tokens per response
  Gemini CLI      ~/.gemini/tmp/*/chats/session-*.json         exact tokens per response
  GitHub Copilot  VS Code logs (GitHub.copilot-chat)           model name per request, no tokens
  Kiro            Kiro logs (kiro.kiroAgent/Kiro Logs.log)     model name per request, no tokens
  Amazon Q        ~/.aws/amazonq/history/chat-history-*.json   model name per answer, no tokens

Only model names, token counts and timestamps are read, never prompts or code.
Files are parsed again only when they change.
"""

import glob
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

from .models_catalog import cloud_model, datacenter_wh, list_cost, provider_of, relative_energy

TOKEN_TYPES = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")

# Extensions that use AI models, and the app name they're measured as (None: they run
# inside VS Code's shared extension host, so they can't be measured on their own).
AI_EXTENSIONS = {
    "anthropic.claude-code": ("Claude Code", "Claude Code"),
    "github.copilot": ("GitHub Copilot", "GitHub Copilot"),
    "github.copilot-chat": ("GitHub Copilot Chat", "GitHub Copilot"),
    "openai.chatgpt": ("Codex", "Codex"),
    "amazonwebservices.amazon-q-vscode": ("Amazon Q", "Amazon Q"),
    "saoudrizwan.claude-dev": ("Cline", None),
    "kodu-ai.claude-dev-experimental": ("Claude Dev (Kodu)", None),
    "andrepimenta.claude-code-chat": ("Claude Code Chat", None),
    "rooveterinaryinc.roo-cline": ("Roo Code", None),
    "continue.continue": ("Continue", None),
    "codeium.codeium": ("Windsurf (Codeium)", None),
    "tabnine.tabnine-vscode": ("Tabnine", None),
    "sourcegraph.cody-ai": ("Cody", None),
    "google.geminicodeassist": ("Gemini Code Assist", None),
    "danielsanmedium.dscodegpt": ("CodeGPT", None),
    "asadbinimtiaz.kiro-vscode-extension": ("Kiro", None),
}

COPILOT_REQUEST = re.compile(r"^(\d{4}-\d{2}-\d{2}) [\d:.]+ \[\w+\] (ccreq:\S+) \| success \| ([\w.\-]+) \|")
KIRO_REQUEST = re.compile(r"^((\d{4}-\d{2}-\d{2}) [\d:.]+) \[\w+\] \[q-developer-converse\] "
                          r"Sending GenerateAssistantResponse modelId=(\S+) agentMode=(\S+)")


def _home(*parts):
    return os.path.join(os.path.expanduser("~"), *parts)


def _logs_dir(app):
    """Logs folder of a VS Code-based editor ("Code", "Kiro", ...)."""
    if sys.platform == "darwin":
        return _home("Library", "Application Support", app, "logs")
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", ""), app, "logs")
    return _home(".config", app, "logs")


def _local_date(iso_ts):
    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone().date().isoformat()


def _ms_date(ms):
    return datetime.fromtimestamp(ms / 1000).date().isoformat()


def parse_claude_code(lines):
    """{response key: (date, model, tokens)}. A response is repeated once per content
    block with the same usage, so it is keyed by message id and request id."""
    out = {}
    for line in lines:
        if '"usage"' not in line or '"assistant"' not in line:
            continue
        try:
            d = json.loads(line)
            msg = d["message"]
            usage, model = msg["usage"], msg["model"]
        except (ValueError, KeyError, TypeError):
            continue
        if not model or model.startswith("<"):  # "<synthetic>" marks local error messages
            continue
        writes = usage.get("cache_creation") or {}
        write_1h = writes.get("ephemeral_1h_input_tokens", 0) or 0
        out[(msg.get("id"), d.get("requestId"))] = (_local_date(d["timestamp"]), model, {
            "input": usage.get("input_tokens", 0) or 0,
            "output": usage.get("output_tokens", 0) or 0,
            "cache_read": usage.get("cache_read_input_tokens", 0) or 0,
            "cache_write_5m": (usage.get("cache_creation_input_tokens", 0) or 0) - write_1h,
            "cache_write_1h": write_1h,
        })
    return out


def parse_codex(lines):
    """{(turn timestamp,): (date, model, tokens)}. Token totals are cumulative per session."""
    out, model, last = {}, None, None
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        payload = d.get("payload") or {}
        if d.get("type") == "turn_context":
            model = payload.get("model") or model
        elif payload.get("type") == "token_count" and model:
            total = (payload.get("info") or {}).get("total_token_usage")
            if not total:
                continue
            cur = (total.get("input_tokens", 0), total.get("cached_input_tokens", 0), total.get("output_tokens", 0))
            prev = last or (0, 0, 0)
            last = cur
            d_in, d_cached, d_out = (max(0, c - p) for c, p in zip(cur, prev))
            if d_in or d_out:
                # OpenAI counts cached tokens inside input_tokens.
                out[(d["timestamp"],)] = (_local_date(d["timestamp"]), model, {
                    "input": max(0, d_in - d_cached), "output": d_out, "cache_read": d_cached})
    return out


def parse_copilot(lines):
    """{(request id,): (date, model, {})}: one entry per successful request, no token counts."""
    out = {}
    for line in lines:
        m = COPILOT_REQUEST.match(line)
        if m:
            out[(m.group(2),)] = (m.group(1), m.group(3), {})
    return out


def parse_opencode(rows):
    """{(message id,): (date, model, tokens)} from OpenCode's assistant messages (JSON rows)."""
    out = {}
    for row in rows:
        try:
            d = json.loads(row)
            model, t, created = d["modelID"], d["tokens"], d["time"]["created"]
        except (ValueError, KeyError, TypeError):
            continue
        cache = t.get("cache") or {}
        tokens = {"input": t.get("input", 0) or 0,
                  "output": (t.get("output", 0) or 0) + (t.get("reasoning", 0) or 0),
                  "cache_read": cache.get("read", 0) or 0,
                  "cache_write_5m": cache.get("write", 0) or 0}
        if model and any(tokens.values()):
            out[(d.get("id"),)] = (_ms_date(created), model, tokens)
    return out


def parse_gemini(lines):
    """{(message id,): (date, model, tokens)} from one Gemini CLI chat session file."""
    try:
        messages = json.loads("".join(lines)).get("messages") or []
    except (ValueError, AttributeError):
        return {}
    out = {}
    for m in messages:
        t, model = m.get("tokens"), m.get("model")
        if m.get("type") != "gemini" or not t or not model:
            continue
        cached = t.get("cached", 0) or 0
        # Gemini counts cached tokens inside input, and bills thinking as output.
        out[(m.get("id"), m.get("timestamp"))] = (_local_date(m["timestamp"]), model, {
            "input": max(0, (t.get("input", 0) or 0) - cached),
            "output": (t.get("output", 0) or 0) + (t.get("thoughts", 0) or 0),
            "cache_read": cached})
    return out


def parse_kiro(lines):
    """{(time,): (date, model, {})}: one entry per agent request, no token counts.
    Intent classification is Kiro's own router call, not the model the user works with."""
    out = {}
    for line in lines:
        m = KIRO_REQUEST.match(line)
        if m and m.group(4) != "intent-classification":
            out[(m.group(1),)] = (m.group(2), m.group(3), {})
    return out


def parse_amazon_q(lines):
    """{(tab, time): (date, model, {})}: one entry per answer, no token counts. The model is
    stored per chat tab; tabs from before Amazon Q had a model picker have none."""
    try:
        collections = json.loads("".join(lines)).get("collections") or []
    except (ValueError, AttributeError):
        return {}
    out = {}
    for tab in (t for c in collections for t in c.get("data") or []):
        model = tab.get("modelId") or "default"
        for conv in tab.get("conversations") or []:
            for msg in conv.get("messages") or []:
                if msg.get("type") == "answer" and msg.get("timestamp"):
                    out[(tab.get("historyId"), msg["timestamp"])] = (_local_date(msg["timestamp"]), model, {})
    return out


SOURCES = [
    # (app, glob pattern, parser)
    ("Claude Code", lambda: [_home(".claude", "projects", "**", "*.jsonl")], parse_claude_code),
    ("Codex", lambda: [_home(".codex", "sessions", "**", "*.jsonl")], parse_codex),
    ("OpenCode", lambda: [_home(".local", "share", "opencode", "opencode.db")], parse_opencode),
    ("Gemini CLI", lambda: [_home(".gemini", "tmp", "*", "chats", "session-*.json")], parse_gemini),
    ("GitHub Copilot", lambda: [os.path.join(_logs_dir("Code"), "*", "window*", "exthost",
                                             "GitHub.copilot-chat", "*.log")], parse_copilot),
    ("Kiro", lambda: [os.path.join(_logs_dir("Kiro"), "*", "window*", "exthost",
                                   "kiro.kiroAgent", "Kiro Logs.log")], parse_kiro),
    ("Amazon Q", lambda: [_home(".aws", "amazonq", "history", "chat-history-*.json")], parse_amazon_q),
]

_cache = {}  # path -> (version, parsed)


def _version(path):
    """(mtime, size) of a file, plus its write-ahead log for SQLite, where new rows land first."""
    paths = [path, path + "-wal"] if path.endswith(".db") else [path]
    return tuple((st.st_mtime, st.st_size) for st in map(os.stat, filter(os.path.exists, paths)))


def _sqlite_messages(path):
    """OpenCode's assistant messages, as JSON rows that include the message id."""
    uri = "file:" + path.replace("?", "%3f").replace("#", "%23") + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=1) as conn:
        return [r[0] for r in conn.execute(
            "SELECT json_set(data, '$.id', id) FROM message WHERE json_extract(data, '$.role') = 'assistant'")]


def _parse_file(path, parser):
    try:
        version = _version(path)
    except OSError:
        return {}
    hit = _cache.get(path)
    if hit and hit[0] == version:
        return hit[1]
    try:
        if path.endswith(".db"):
            parsed = parser(_sqlite_messages(path))
        else:
            with open(path, encoding="utf-8", errors="ignore") as f:
                parsed = parser(f)
    except (OSError, sqlite3.Error):
        parsed = {}
    _cache[path] = (version, parsed)
    return parsed


def scan_events(days=30, sources=None):
    """[(app, date, model, tokens)] from every log on this device, newer than `days`."""
    since = (date.today() - timedelta(days=days)).isoformat()
    events = []
    for app, patterns, parser in sources or SOURCES:
        merged = {}
        for pattern in patterns():
            for path in glob.glob(pattern, recursive=True):
                # Claude Code can copy responses into a resumed session's file; keys dedupe them.
                merged.update(_parse_file(path, parser))
        events += [(app, day, model, tokens) for day, model, tokens in merged.values() if day >= since]
    return events


def _with_estimates(row):
    has_tokens = any(row["tokens"].values())
    cost = list_cost(row["model"], row["tokens"]) if has_tokens else None
    wh = datacenter_wh(row["model"], row["tokens"]) if has_tokens else None
    info = cloud_model(row["model"])
    approximate = bool(info and info["approximate"])
    return {**row,
            # A model only matched by family keeps its own id as its name.
            "name": info["name"] if info and not approximate else row["model"],
            "provider": provider_of(row["model"]),
            "priced_as": info["name"] if approximate else None,
            "list_cost_usd": None if cost is None else round(cost, 4),
            "datacenter_wh": None if wh is None else round(wh, 2),
            "relative_energy": relative_energy(row["model"]),
            "source": "estimated"}


def summarize(events):
    """Totals per (app, model) and per (date, app, model), with data-center estimates."""
    totals, daily = {}, {}
    for app, day, model, tokens in events:
        for key, table in (((app, model), totals), ((day, app, model), daily)):
            row = table.setdefault(key, {"app": app, "model": model, "requests": 0,
                                         "tokens": dict.fromkeys(TOKEN_TYPES, 0)})
            row["requests"] += 1
            for t, n in tokens.items():
                row["tokens"][t] += n
        daily[(day, app, model)]["date"] = day
    models = sorted((_with_estimates(r) for r in totals.values()),
                    key=lambda r: (r["datacenter_wh"] or 0, r["requests"]), reverse=True)
    days = [{k: v for k, v in _with_estimates(r).items() if k in ("date", "app", "model", "requests", "datacenter_wh")}
            for r in sorted(daily.values(), key=lambda r: r["date"])]
    return models, days


def switch_hint(models):
    """How much of the data-center estimate would go if Opus-class work moved to Sonnet 5.5."""
    total = sum(m["datacenter_wh"] or 0 for m in models)
    big = [m for m in models if (m["relative_energy"] or 0) > 1 and m["datacenter_wh"]]
    big_wh = sum(m["datacenter_wh"] for m in big)
    if not total or big_wh / total < 0.5:
        return None
    saved = sum(m["datacenter_wh"] * (1 - 1 / m["relative_energy"]) for m in big) / 2  # half the tasks are simple
    return {
        "share": round(big_wh / total, 3),
        "models": [m["name"] for m in big],
        "wh_saved": round(saved, 1),
        "message": f"{big_wh / total:.0%} of your estimated data-center energy went to "
                   f"{', '.join(sorted({m['name'] for m in big}))}. Moving simple tasks to Sonnet 5.5 "
                   f"would save about {saved:,.0f} Wh. Not on your bill.",
    }


def installed_extensions(ext_dir=None):
    """AI extensions installed in VS Code, and whether each can be measured on its own."""
    ext_dir = ext_dir or _home(".vscode", "extensions")
    try:
        names = os.listdir(ext_dir)
    except OSError:
        return []
    found = {}
    for entry in names:
        ext_id = re.sub(r"-\d+(\.\d+)*.*$", "", entry.lower())
        if ext_id in AI_EXTENSIONS:
            name, app = AI_EXTENSIONS[ext_id]
            found[ext_id] = {"id": ext_id, "name": name, "measured_as": app, "measurable": app is not None}
    return sorted(found.values(), key=lambda e: (not e["measurable"], e["name"]))


def _mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0


def latest_models(sources=None):
    """The model of each app's most recent response, from its newest log: {app: model id}."""
    out = {}
    for app, patterns, parser in sources or SOURCES:
        paths = [p for pattern in patterns() for p in glob.glob(pattern, recursive=True)]
        if not paths:
            continue
        parsed = _parse_file(max(paths, key=_mtime), parser)
        if parsed:
            out[app] = list(parsed.values())[-1][1]
    return out


def model_usage(days=30):
    events = scan_events(days)
    models, daily = summarize(events)
    return {"days": days, "models": models, "daily": daily, "switch_hint": switch_hint(models),
            "extensions": installed_extensions()}
