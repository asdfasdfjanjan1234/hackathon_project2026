"""Usage levels and when they happen, from a device's hourly AI energy (readings.py).

Each measured hour gets a level from its average AI power (Wh in an hour = average watts):

    idle       below ACTIVE_W: AI apps open, but not working
    light      the lowest third of this device's active hours
    moderate   the middle third
    heavy      the top third

The cut points are this device's own 33rd and 67th percentiles of active hours, so "heavy" means
heavy for this machine, whether it's a laptop on Claude Code or a desktop running a 70B model.

Each AI agent (readings.agent_series) also gets its own summary: how much of the energy it uses, how
many hours it's in use, how heavily, and at what times of day on weekdays and weekends.
"""

import numpy as np
import pandas as pd

from app.services.cheap_hours import is_peak

from .config import CONFIG
from .readings import USED_WH

ACTIVE_W = CONFIG["levels"]["active_w"]
LEVELS = ("idle", "light", "moderate", "heavy")
MIN_PAIRS = 24  # hour pairs needed to report an autocorrelation


def thresholds(wh):
    active = wh.dropna()
    active = active[active >= ACTIVE_W]
    if active.empty:
        return {"active_w": ACTIVE_W, "light_max_w": None, "moderate_max_w": None}
    return {"active_w": ACTIVE_W, "light_max_w": round(float(active.quantile(1 / 3)), 3),
            "moderate_max_w": round(float(active.quantile(2 / 3)), 3)}


def level_of(wh, th):
    def one(w):
        if pd.isna(w):
            return None
        if w < th["active_w"]:
            return "idle"
        if th["light_max_w"] is None or w <= th["light_max_w"]:
            return "light"
        return "moderate" if w <= th["moderate_max_w"] else "heavy"

    return pd.Series([one(w) for w in wh], index=wh.index, dtype=object)


def seasonality(y):
    """How much each hour resembles the same hour a day and a week earlier (log scale), or None."""
    z = np.log1p(y.clip(lower=0))
    out = {}
    for name, lag in (("daily", 24), ("weekly", 168)):
        pairs = (z.notna() & z.shift(lag).notna()).sum()
        out[name] = round(float(z.autocorr(lag)), 3) if pairs >= MIN_PAIRS else None
    return out


def hour_profile(y, active_w=None):
    """Per hour of day: average on weekdays and weekends, and (for devices) the share of hours active."""
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
        y = agents[name].dropna()
        used = y[y >= USED_WH]
        by_hour = y.groupby(y.index.hour).mean().sort_values(ascending=False)
        weekend = y.index.dayofweek >= 5
        peak = [is_peak(t.dayofweek, t.hour) for t in y.index]
        out.append({
            "agent": name, "kwh": _round(y.sum() / 1000, 5),
            "share_of_energy": _round(y.sum() / total) if total else None,
            "hours_used": int(len(used)), "share_of_hours_used": _round(len(used) / len(y)) if len(y) else None,
            "avg_w_when_used": _round(used.mean()) if len(used) else None,
            "weekday_avg_w": _round(y[~weekend].mean()), "weekend_avg_w": _round(y[weekend].mean()),
            "busiest_hours": [int(h) for h in by_hour.head(3).index] if y.sum() > 0 else [],
            "energy_in_meralco_peak_hours": _round(y[peak].sum() / y.sum()) if y.sum() > 0 else None,
            "profile": hour_profile(agents[name]),
        })
    return out


def study_device(hourly, by_app, agents):
    """Everything 03_study_patterns.py reports for a device."""
    wh = hourly["wh"]
    obs = wh.dropna()
    if obs.empty:
        raise ValueError("No measured hours yet: run the device reader, then 02_export_readings.py")
    th = thresholds(obs)
    level = level_of(obs, th)
    energy = hourly["ai_wh"]
    total_wh = float(energy.sum())
    by_app = by_app.copy()
    by_app["level"] = by_app["hour"].map(level)
    levels = []
    for name in LEVELS:
        hours = level.index[level == name]
        apps = (by_app[by_app["level"] == name].groupby("app")["wh"].sum().sort_values(ascending=False))
        levels.append({
            "level": name, "hours": int(len(hours)), "share_of_hours": _round(len(hours) / len(obs)),
            "avg_w": _round(obs[hours].mean()) if len(hours) else None,
            "kwh": _round(energy[hours].sum() / 1000, 5),
            "share_of_energy": _round(energy[hours].sum() / total_wh) if total_wh else None,
            "top_agents": [{"name": n, "kwh": _round(v / 1000, 5)} for n, v in apps.head(3).items()],
        })
    profile = hour_profile(wh, ACTIVE_W)
    for row in profile:
        at = level[level.index.hour == row["hour"]]
        row["usual_level"] = at.mode().iloc[0] if not at.empty else None
    mean_by_hour = obs.groupby(obs.index.hour).mean().sort_values(ascending=False)
    peak_wh = float(energy[[is_peak(t.dayofweek, t.hour) for t in energy.index]].sum()) if total_wh else 0.0
    return {
        "coverage": {"first": str(wh.index[0]), "last": str(wh.index[-1]), "measured_hours": int(len(obs)),
                     "days_with_readings": int(pd.Index(obs.index.date).nunique()),
                     "reader_hours": _round(hourly["measured_h"].sum(), 2)},
        "thresholds_w": th,
        "levels": levels,
        "busiest_hours": [{"hour": int(h), "avg_w": _round(v)} for h, v in mean_by_hour.head(3).items()],
        "energy_in_meralco_peak_hours": _round(peak_wh / total_wh) if total_wh else None,
        "seasonality": seasonality(wh),
        "profile": profile,
        "total_kwh": _round(total_wh / 1000, 5),
        "agents": study_agents(agents),
    }


def study_grid(mwh):
    obs = mwh.dropna()
    return {"coverage": {"first": str(mwh.index[0]), "last": str(mwh.index[-1]), "measured_hours": int(len(obs))},
            "avg_mw": _round(obs.mean(), 1), "peak_mw": _round(obs.max(), 1),
            "peak_at": str(obs.idxmax()), "seasonality": seasonality(mwh), "profile": hour_profile(mwh)}


def _hour_label(h):
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


def _fmt(v, unit=""):
    return "–" if v is None else f"{v:,.3f}{unit}"


def device_markdown(device_id, r):
    c, th = r["coverage"], r["thresholds_w"]
    lines = [
        f"# AI usage patterns: device {device_id}", "",
        f"Readings from {c['first']} to {c['last']}: {c['measured_hours']} measured hours on "
        f"{c['days_with_readings']} days. AI energy measured: {_fmt(r['total_kwh'], ' kWh')}.", "",
        "## Usage levels", "",
        f"Idle is below {th['active_w']} W of AI power. Light is up to {_fmt(th['light_max_w'], ' W')}, "
        f"moderate up to {_fmt(th['moderate_max_w'], ' W')}, heavy above that (this device's own thirds).", "",
        "| Level | Hours | Share of hours | Avg W | kWh | Share of energy | Top agents |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for lv in r["levels"]:
        apps = ", ".join(a["name"] for a in lv["top_agents"]) or "–"
        lines.append(f"| {lv['level']} | {lv['hours']} | {_fmt(lv['share_of_hours'])} | {_fmt(lv['avg_w'])} | "
                     f"{_fmt(lv['kwh'])} | {_fmt(lv['share_of_energy'])} | {apps} |")
    lines += ["", "## AI agents", "",
              "| Agent | kWh | Share of energy | Hours in use | Avg W in use | Weekday avg W | Weekend avg W | "
              "Busiest hours | Energy in Meralco peak hours |", "|---|---:|---:|---:|---:|---:|---:|---|---:|"]
    for a in r["agents"]:
        busiest = ", ".join(_hour_label(h) for h in a["busiest_hours"]) or "–"
        lines.append(f"| {a['agent']} | {_fmt(a['kwh'])} | {_fmt(a['share_of_energy'])} | {a['hours_used']} | "
                     f"{_fmt(a['avg_w_when_used'])} | {_fmt(a['weekday_avg_w'])} | {_fmt(a['weekend_avg_w'])} | "
                     f"{busiest} | {_fmt(a['energy_in_meralco_peak_hours'])} |")
    s = r["seasonality"]
    lines += [
        "", "## When", "",
        "Busiest hours: " + ", ".join(f"{_hour_label(b['hour'])} ({_fmt(b['avg_w'], ' W')})" for b in r["busiest_hours"]) + ".",
        f"Share of AI energy in Meralco Peak/Off-Peak peak hours: {_fmt(r['energy_in_meralco_peak_hours'])}.",
        f"Same hour a day earlier, correlation: {_fmt(s['daily'])}; a week earlier: {_fmt(s['weekly'])} "
        "(near 1: a strong daily/weekly routine for the seasonal model to use; near 0: little pattern).",
        "", "| Hour | Weekday avg W | Weekend avg W | Share of hours active | Usual level |",
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
        f"{c['first']} to {c['last']}: {c['measured_hours']} hours. Average {r['avg_mw']:,.1f} MW, "
        f"peak {r['peak_mw']:,.1f} MW at {r['peak_at']}.",
        f"Correlation with the same hour a day earlier: {_fmt(s['daily'])}; a week earlier: {_fmt(s['weekly'])}.",
        "", "| Hour | Weekday avg MW | Weekend avg MW |", "|---|---:|---:|",
    ]
    lines += [f"| {_hour_label(p['hour'])} | {_fmt(p['weekday'])} | {_fmt(p['weekend'])} |" for p in r["profile"]]
    return "\n".join(lines) + "\n"
