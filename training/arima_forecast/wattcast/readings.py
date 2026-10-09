"""A device's AI energy by clock hour and by AI agent, from the backend's readings database.

For each hour:
    measured_h  share of the hour the device reader ran (samples.interval_s / 3600, at most 1)
    ai_wh       AI energy measured in that time: sum of ai_samples.watts x interval_s, in Wh.
                Every row in ai_samples is power drawn on this device, so all of it is on the bill.
    wh          what the model fits: ai_wh, or missing (NaN) when the hour is unknown

An agent is ai_samples.app (Claude Code, GitHub Copilot, Ollama, ...): its models and the commands
it runs ("tool runs") are all that agent's energy.

Which hours are unknown (`gaps`):
    "day"      (default) a day the reader ran at least MIN_DAY_HOURS: its hours without readings
               count as no AI use (computer off or asleep), as in the backend's daily totals.
               A day with no readings is unknown.
    "missing"  only hours the reader ran at least MIN_COVERAGE of count, scaled up to the full hour;
               every other hour is unknown.
    "zero"     every hour without readings counts as no AI use.
"""

import pandas as pd

from .config import CONFIG
from .settings import TZ

MIN_COVERAGE = CONFIG["device"]["min_coverage"]
MIN_DAY_HOURS = CONFIG["device"]["min_day_hours"]
GAPS = ("day", "missing", "zero")
OTHER = "Other AI apps"
# An agent gets its own model with this many hours of use and this share of the AI energy;
# smaller ones are forecast together as OTHER.
USED_WH = CONFIG["agents"]["used_wh"]
MIN_USED_HOURS = CONFIG["agents"]["min_used_hours"]
MIN_SHARE = CONFIG["agents"]["min_share"]
MAX_AGENTS = CONFIG["agents"]["max_agents"]


def _frame(conn, sql, params):
    return pd.DataFrame([dict(r) for r in conn.execute(sql, params).fetchall()])


def _hour(ts):
    return pd.to_datetime(ts, unit="s", utc=True).dt.tz_convert(TZ).dt.tz_localize(None).dt.floor("h")


def _scale(measured, gaps):
    """What to multiply an hour's measured Wh by to get the modeled value; NaN where unknown."""
    if gaps == "zero":
        return pd.Series(1.0, index=measured.index)
    if gaps == "missing":
        return (1 / measured).where(measured >= MIN_COVERAGE)
    day_hours = measured.groupby(measured.index.date).transform("sum")
    return pd.Series(1.0, index=measured.index).where(day_hours >= MIN_DAY_HOURS)


def hourly_ai_energy(conn, device_id, gaps=CONFIG["device"]["gaps"]):
    """(hourly, by_app): the hourly table above (plus `scale`), and measured Wh per hour, agent and model."""
    if gaps not in GAPS:
        raise ValueError(f"gaps must be one of {GAPS}")
    empty_apps = pd.DataFrame(columns=["hour", "app", "name", "kind", "wh"])
    samples = _frame(conn, "SELECT ts, interval_s FROM samples WHERE device_id = ?", (device_id,))
    if samples.empty:
        return pd.DataFrame(columns=["measured_h", "ai_wh", "scale", "wh"]), empty_apps
    apps = _frame(conn, "SELECT ts, interval_s, watts, kind, app, COALESCE(model, app) AS name "
                        "FROM ai_samples WHERE device_id = ?", (device_id,))
    measured = samples["interval_s"].groupby(_hour(samples["ts"])).sum() / 3600
    hours = pd.date_range(measured.index.min(), measured.index.max(), freq="h")
    hourly = pd.DataFrame(index=hours)
    hourly["measured_h"] = measured.reindex(hours).fillna(0.0).clip(upper=1.0)
    if apps.empty:
        hourly["ai_wh"] = 0.0
        by_app = empty_apps
    else:
        apps["hour"] = _hour(apps["ts"])
        apps["wh"] = apps["watts"].astype(float) * apps["interval_s"].astype(float) / 3600
        hourly["ai_wh"] = apps.groupby("hour")["wh"].sum().reindex(hours).fillna(0.0)
        by_app = apps.groupby(["hour", "app", "name", "kind"], as_index=False)["wh"].sum()
    hourly["scale"] = _scale(hourly["measured_h"], gaps)
    hourly["wh"] = hourly["ai_wh"] * hourly["scale"]
    hourly.index.name = "hour"
    return hourly, by_app


def agent_series(hourly, by_app):
    """One column of hourly Wh per AI agent, unknown hours as NaN, biggest agent first. Agents with
    little use or energy are added up in an OTHER column. The columns sum to hourly["wh"]."""
    if by_app.empty:
        return pd.DataFrame({OTHER: hourly["wh"]})
    wide = (by_app.pivot_table(index="hour", columns="app", values="wh", aggfunc="sum")
            .reindex(hourly.index).fillna(0.0))
    total = wide.sum().sum()
    own = [a for a in wide.sum().sort_values(ascending=False).index
           if (wide[a] >= USED_WH).sum() >= MIN_USED_HOURS and total > 0 and wide[a].sum() / total >= MIN_SHARE]
    own = own[:MAX_AGENTS]
    out = wide[own].copy()
    rest = wide.drop(columns=own).sum(axis=1)
    if rest.sum() > 0 or not own:
        out[OTHER] = rest
    out = out.mul(hourly["scale"], axis=0)
    out.columns.name = None
    return out


def load_hourly(path):
    """The hourly table saved by 02_export_readings.py, with a regular hourly index."""
    return pd.read_csv(path, parse_dates=["hour"], index_col="hour").asfreq("h")


def load_by_app(path):
    return pd.read_csv(path, parse_dates=["hour"])
