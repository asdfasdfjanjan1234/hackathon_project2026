"""Cleanest hours of the day to run heavy AI jobs, from the grid's hourly carbon intensity.

The grid's carbon intensity (g CO2 per kWh) changes through the day with what's generating:
solar at midday, peaking plants in the evening. The same job emits less in a cleaner hour.

  grid profile  Electricity Maps' carbon intensity for the user's zone (a free personal token):
                the forecast for the next 24 hours when the token's plan has it, else the last
                24 hours, read as "tomorrow looks like today". Without a token there's no hourly
                data, and nothing here is made up to fill the gap.
  your use      AI kWh by hour of day on this device, averaged over the days measured
  the shift     SHIFTABLE_SHARE of AI energy (batch work that can wait) moved from the hours it
                runs now to the cleanest CLEAN_WINDOW_HOURS-hour window

On a flat-rate bill shifting saves CO2, not money. Intensities are Electricity Maps' lifecycle
figures, so they rank hours of this grid; the DOE factor stays the basis of the CO2 totals.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime

API = "https://api.electricitymap.org/v3/carbon-intensity"
CACHE_S = 900           # Electricity Maps updates hourly
ERROR_CACHE_S = 60      # retry a failed fetch sooner
SHIFTABLE_SHARE = 0.3   # assumed share of AI energy that's batch work: evals, indexing, long agent runs
MIN_HOURS = 20          # hours of grid data needed for a day's profile
MIN_GAP = 0.05          # the clean window must be this much cleaner than the hours used now

_cache = {}


def _get(path, zone, token, timeout=5):
    req = urllib.request.Request(f"{API}/{path}?zone={zone}", headers={"auth-token": token})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def _local(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()


def _error(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            return json.load(e).get("message") or f"HTTP {e.code}"
        except ValueError:
            return f"HTTP {e.code}"
    return str(getattr(e, "reason", e))


def _fetch(zone, token):
    points, source, error = [], None, None
    for path, key in (("forecast", "forecast"), ("history", "history")):
        try:
            points, source = _get(path, zone, token)[key], path
            break
        except (OSError, ValueError, KeyError) as e:  # URLError and HTTPError are OSErrors
            error = _error(e)
    points = sorted(points, key=lambda p: p["datetime"])
    if source == "forecast":
        points = points[:24]
    by_hour = {}
    for p in points:
        if p.get("carbonIntensity") is not None:
            by_hour[_local(p["datetime"]).hour] = p["carbonIntensity"]  # history: the latest reading wins
    now = None
    try:
        latest = _get("latest", zone, token)
        now = {"g_per_kwh": latest["carbonIntensity"], "datetime": _local(latest["datetime"]).isoformat()}
    except (OSError, ValueError, KeyError):
        pass
    return {"source": source if by_hour else None, "by_hour": by_hour, "now": now,
            "error": None if by_hour else error}


def grid_profile(zone, token):
    """{source: "forecast" | "history" | None, by_hour: {hour: g/kWh}, now, error}, cached."""
    hit = _cache.get((zone, token))
    if hit and time.time() < hit[0]:
        return hit[1]
    result = _fetch(zone, token)
    _cache[(zone, token)] = (time.time() + (CACHE_S if result["by_hour"] else ERROR_CACHE_S), result)
    return result


def _window(start, hours):
    return [(start + i) % 24 for i in range(hours)]


def _hour_label(h):
    return f"{h % 12 or 12} {'AM' if h % 24 < 12 else 'PM'}"


def plan(use_by_hour, intensity, window_hours=3):
    """The cleanest and dirtiest windows of the day, and what moving batch work to the cleanest saves.

    use_by_hour: {hour: average kWh a day}. intensity: {hour: g CO2/kWh}.
    """
    windows = [(sum(intensity[h] for h in _window(s, window_hours)) / window_hours, s) for s in range(24)
               if all(h in intensity for h in _window(s, window_hours))]
    if len(intensity) < MIN_HOURS or not windows:
        return None
    (clean_g, clean_start), (dirty_g, dirty_start) = min(windows), max(windows)
    used = {h: kwh for h, kwh in use_by_hour.items() if kwh > 0 and h in intensity}
    daily_kwh = sum(used.values())
    weighted = sum(kwh * intensity[h] for h, kwh in used.items()) / daily_kwh if daily_kwh else None
    peak = max(used, key=used.get) if used else None

    shift = None
    if weighted and weighted - clean_g > MIN_GAP * weighted:
        kwh_month = daily_kwh * 30 * SHIFTABLE_SHARE
        shift = {"share": SHIFTABLE_SHARE, "kwh_month": round(kwh_month, 4),
                 "g_per_kwh_saved": round(weighted - clean_g, 1),
                 "co2_saved_kg": round(kwh_month * (weighted - clean_g) / 1000, 4)}

    def describe(start, g):
        end = (start + window_hours) % 24
        return {"start_hour": start, "end_hour": end, "g_per_kwh": round(g, 1),
                "label": f"{_hour_label(start)} – {_hour_label(end)}"}

    return {
        "window_hours": window_hours,
        "cleanest": describe(clean_start, clean_g),
        "dirtiest": describe(dirty_start, dirty_g),
        "weighted_g_per_kwh": None if weighted is None else round(weighted, 1),
        "peak_use_hour": peak,
        "peak_use_label": None if peak is None else _hour_label(peak),
        "shift": shift,
    }


def clean_hours(use_by_hour, cfg):
    """Everything the dashboard and the "clean hours" recommendation need, from the app config."""
    token, zone = cfg.get("ELECTRICITYMAPS_TOKEN"), cfg.get("ELECTRICITYMAPS_ZONE")
    base = {"configured": bool(token), "zone": zone,
            "use": [{"hour": h, "kwh_per_day": round(use_by_hour.get(h, 0.0), 6)} for h in range(24)]}
    if not token:
        return {**base, "source": None, "intensity": [], "now": None, "plan": None,
                "error": "Set ELECTRICITYMAPS_TOKEN in backend/.env for hourly grid data."}
    grid = grid_profile(zone, token)
    return {**base, "source": grid["source"], "now": grid["now"], "error": grid["error"],
            "intensity": [{"hour": h, "g_per_kwh": grid["by_hour"].get(h)} for h in range(24)],
            "plan": plan(use_by_hour, grid["by_hour"], cfg.get("CLEAN_WINDOW_HOURS", 3))}


def clean_hours_rec(info):
    """The "clean hours" recommendation, or None when there's no hourly data or nothing to gain."""
    p = info and info.get("plan")
    if not p or not p["shift"]:
        return None
    s, c = p["shift"], p["cleanest"]
    basis = "forecast" if info["source"] == "forecast" else "last 24 hours"
    return {
        "action": "SWITCH", "rule": "clean hours", "model": "All AI workloads",
        "message": (f"Your AI use peaks around {p['peak_use_label']}, when the {info['zone']} grid averages "
                    f"{p['weighted_g_per_kwh']:,.0f} g CO₂/kWh for your hours. It's cleanest {c['label']} "
                    f"({c['g_per_kwh']:,.0f} g, {basis}). Running batch jobs then (evals, indexing, long agent "
                    f"runs) avoids about {s['co2_saved_kg'] * 1000:,.0f} g CO₂ a month. Your bill doesn't change."),
        "monthly_savings": 0.0, "scope": "carbon", "alternative": False,
        "co2_saved_kg": s["co2_saved_kg"], "window": c,
    }
