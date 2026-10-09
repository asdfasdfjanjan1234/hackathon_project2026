"""Usage levels and when they happen, from a device's AI energy per time step (readings.py).

Each measured step gets a level from its average AI power (watts(): its Wh times the steps in an hour):

    idle       below ACTIVE_W: AI apps open, but not working
    light      the lowest third of this device's active steps
    moderate   the middle third
    heavy      the top third

The cut points are this device's own 33rd and 67th percentiles of active steps, so "heavy" means
heavy for this machine, whether it's a laptop on Claude Code or a desktop running a 70B model.

Each AI agent (readings.agent_series) also gets its own summary: how much of the energy it uses, how
many hours it's in use, how heavily, and at what times of day on weekdays and weekends.
"""

import numpy as np
import pandas as pd

from app.services.cheap_hours import is_peak

from .config import CONFIG
from .readings import USED_WH
from .steps import hours, per_hour

ACTIVE_W = CONFIG["levels"]["active_w"]
LEVELS = ("idle", "light", "moderate", "heavy")
MIN_PAIRS = 24  # hours of pairs needed to report an autocorrelation


def watts(wh):
    """Average power (W) in each step, from a series of Wh per step."""
    return wh * per_hour(wh.index)


def thresholds(w):
    """The level cut points, from a series of average W per step."""
    active = w.dropna()
    active = active[active >= ACTIVE_W]
    if active.empty:
        return {"active_w": ACTIVE_W, "light_max_w": None, "moderate_max_w": None}
    return {"active_w": ACTIVE_W, "light_max_w": round(float(active.quantile(1 / 3)), 3),
            "moderate_max_w": round(float(active.quantile(2 / 3)), 3)}


def level_of(w, th):
    """The usage level of each step, from a series of average W."""
    def one(w):
        if pd.isna(w):
            return None
        if w < th["active_w"]:
            return "idle"
        if th["light_max_w"] is None or w <= th["light_max_w"]:
            return "light"
        return "moderate" if w <= th["moderate_max_w"] else "heavy"

    return pd.Series([one(v) for v in w], index=w.index, dtype=object)


def seasonality(y):
    """How much each step resembles the same time a day and a week earlier (log scale), or None."""
    z = np.log1p(y.clip(lower=0))
    n = per_hour(y.index)
    out = {}
    for name, lag in (("daily", 24 * n), ("weekly", 168 * n)):
        pairs = (z.notna() & z.shift(lag).notna()).sum()
        out[name] = round(float(z.autocorr(lag)), 3) if pairs >= MIN_PAIRS * n else None
    return out


def hour_profile(y, active_w=None):
    """Per hour of day: average on weekdays and weekends, and (for devices, in W) the share of steps active."""
    obs = y.dropna()
    weekend = obs.index.dayofweek >= 5
    rows = []
    for h in range(24):
        at = obs.index.hour == h
        row = {"hour": h,
               "weekday": _round(obs[at & ~weekend].mean()),
               "weekend": _round(obs[at & weekend].mean())}
        if active_w is not None:
            row["active_share"] = _round((obs[at] >= active_w).mean()) if at.any() else None
        rows.append(row)
    return rows


def _round(v, n=3):
    return None if v is None or pd.isna(v) else round(float(v), n)


def study_agents(agents):
    """Per agent (a column of readings.agent_series): energy, hours in use, how heavily, and when."""
    total = float(agents.sum().sum())
    out = []
    for name in agents.columns:
        y, w = agents[name].dropna(), watts(agents[name]).dropna()
        used = w[w >= USED_WH]
        by_hour = w.groupby(w.index.hour).mean().sort_values(ascending=False)
        weekend = w.index.dayofweek >= 5
        peak = [is_peak(t.dayofweek, t.hour) for t in y.index]
        out.append({
            "agent": name, "kwh": _round(y.sum() / 1000, 5),
            "share_of_energy": _round(y.sum() / total) if total else None,
            "hours_used": hours(len(used), agents.index),
            "share_of_hours_used": _round(len(used) / len(y)) if len(y) else None,
            "avg_w_when_used": _round(used.mean()) if len(used) else None,
            "weekday_avg_w": _round(w[~weekend].mean()), "weekend_avg_w": _round(w[weekend].mean()),
            "busiest_hours": [int(h) for h in by_hour.head(3).index] if y.sum() > 0 else [],
            "energy_in_meralco_peak_hours": _round(y[peak].sum() / y.sum()) if y.sum() > 0 else None,
            "profile": hour_profile(watts(agents[name])),
        })
    return out


def study_device(energy, by_app, agents):
    """Everything 03_study_patterns.py reports for a device (energy, by_app: readings.ai_energy)."""
    wh = energy["wh"]
    obs = watts(wh).dropna()
    if obs.empty:
        raise ValueError("No measured steps yet: run the device reader, then 02_export_readings.py")
    th = thresholds(obs)
    level = level_of(obs, th)
    measured = energy["ai_wh"]
    total_wh = float(measured.sum())
    by_app = by_app.copy()
    by_app["level"] = by_app["time"].map(level)
    levels = []
    for name in LEVELS:
        at = level.index[level == name]
        apps = (by_app[by_app["level"] == name].groupby("app")["wh"].sum().sort_values(ascending=False))
        levels.append({
            "level": name, "hours": hours(len(at), wh.index), "share_of_hours": _round(len(at) / len(obs)),
            "avg_w": _round(obs[at].mean()) if len(at) else None,
            "kwh": _round(measured[at].sum() / 1000, 5),
            "share_of_energy": _round(measured[at].sum() / total_wh) if total_wh else None,
            "top_agents": [{"name": n, "kwh": _round(v / 1000, 5)} for n, v in apps.head(3).items()],
        })
    profile = hour_profile(watts(wh), ACTIVE_W)
    for row in profile:
        at = level[level.index.hour == row["hour"]]
        row["usual_level"] = at.mode().iloc[0] if not at.empty else None
    mean_by_hour = obs.groupby(obs.index.hour).mean().sort_values(ascending=False)
    peak_wh = float(measured[[is_peak(t.dayofweek, t.hour) for t in measured.index]].sum()) if total_wh else 0.0
    return {
        "coverage": {"first": str(wh.index[0]), "last": str(wh.index[-1]),
                     "step_minutes": round(60 / per_hour(wh.index)), "measured_hours": hours(len(obs), wh.index),
                     "days_with_readings": int(pd.Index(obs.index.date).nunique()),
                     "reader_hours": _round(energy["measured_h"].sum(), 2)},
        "thresholds_w": th,
        "levels": levels,
        "busiest_hours": [{"hour": int(h), "avg_w": _round(v)} for h, v in mean_by_hour.head(3).items()],
        "energy_in_meralco_peak_hours": _round(peak_wh / total_wh) if total_wh else None,
        "seasonality": seasonality(wh),
        "profile": profile,
        "total_kwh": _round(total_wh / 1000, 5),
        "agents": study_agents(agents),
    }


def study_grid(mw):
    obs = mw.dropna()
    return {"coverage": {"first": str(mw.index[0]), "last": str(mw.index[-1]),
                         "measured_hours": hours(len(obs), mw.index)},
            "avg_mw": _round(obs.mean(), 1), "peak_mw": _round(obs.max(), 1),
            "peak_at": str(obs.idxmax()), "seasonality": seasonality(mw), "profile": hour_profile(mw)}


def _hour_label(h):
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def _fmt(v, unit=""):
    return "–" if v is None else f"{v:,.3f}{unit}"


def device_markdown(device_id, r):
    c, th = r["coverage"], r["thresholds_w"]
    lines = [
        f"# AI usage patterns: device {device_id}", "",
        f"Readings from {c['first']} to {c['last']}, in {c['step_minutes']}-minute steps: "
        f"{c['measured_hours']:g} measured hours on "
        f"{c['days_with_readings']} days. AI energy measured: {_fmt(r['total_kwh'], ' kWh')}.", "",
        "## Usage levels", "",
        f"Idle is below {th['active_w']} W of AI power. Light is up to {_fmt(th['light_max_w'], ' W')}, "
        f"moderate up to {_fmt(th['moderate_max_w'], ' W')}, heavy above that (this device's own thirds).", "",
        "| Level | Hours | Share of hours | Avg W | kWh | Share of energy | Top agents |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for lv in r["levels"]:
        apps = ", ".join(a["name"] for a in lv["top_agents"]) or "–"
        lines.append(f"| {lv['level']} | {lv['hours']:g} | {_fmt(lv['share_of_hours'])} | {_fmt(lv['avg_w'])} | "
                     f"{_fmt(lv['kwh'])} | {_fmt(lv['share_of_energy'])} | {apps} |")
    lines += ["", "## AI agents", "",
              "| Agent | kWh | Share of energy | Hours in use | Avg W in use | Weekday avg W | Weekend avg W | "
              "Busiest hours | Energy in Meralco peak hours |", "|---|---:|---:|---:|---:|---:|---:|---|---:|"]
    for a in r["agents"]:
        busiest = ", ".join(_hour_label(h) for h in a["busiest_hours"]) or "–"
        lines.append(f"| {a['agent']} | {_fmt(a['kwh'])} | {_fmt(a['share_of_energy'])} | {a['hours_used']:g} | "
                     f"{_fmt(a['avg_w_when_used'])} | {_fmt(a['weekday_avg_w'])} | {_fmt(a['weekend_avg_w'])} | "
                     f"{busiest} | {_fmt(a['energy_in_meralco_peak_hours'])} |")
    s = r["seasonality"]
    lines += [
        "", "## When", "",
        "Busiest hours: " + ", ".join(f"{_hour_label(b['hour'])} ({_fmt(b['avg_w'], ' W')})" for b in r["busiest_hours"]) + ".",
        f"Share of AI energy in Meralco Peak/Off-Peak peak hours: {_fmt(r['energy_in_meralco_peak_hours'])}.",
        f"Same time a day earlier, correlation: {_fmt(s['daily'])}; a week earlier: {_fmt(s['weekly'])} "
        "(near 1: a strong daily/weekly routine for the seasonal model to use; near 0: little pattern).",
        "", "| Hour | Weekday avg W | Weekend avg W | Share of time active | Usual level |",
        "|---|---:|---:|---:|---|",
    ]
    for p in r["profile"]:
        lines.append(f"| {_hour_label(p['hour'])} | {_fmt(p['weekday'])} | {_fmt(p['weekend'])} | "
                     f"{_fmt(p['active_share'])} | {p['usual_level'] or '–'} |")
    return "\n".join(lines) + "\n"


def grid_markdown(r):
    c, s = r["coverage"], r["seasonality"]
    lines = [
        "# Luzon grid demand patterns (IEMOP)", "",
        f"{c['first']} to {c['last']}: {c['measured_hours']:g} hours. Average {r['avg_mw']:,.1f} MW, "
        f"peak {r['peak_mw']:,.1f} MW at {r['peak_at']}.",
        f"Correlation with the same time a day earlier: {_fmt(s['daily'])}; a week earlier: {_fmt(s['weekly'])}.",
        "", "| Hour | Weekday avg MW | Weekend avg MW |", "|---|---:|---:|",
    ]
    lines += [f"| {_hour_label(p['hour'])} | {_fmt(p['weekday'])} | {_fmt(p['weekend'])} |" for p in r["profile"]]
    return "\n".join(lines) + "\n"
