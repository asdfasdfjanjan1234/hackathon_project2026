"""A device's AI energy by time step and by AI agent, from the backend's readings database.

A step is `step_minutes` of clock time (config.json; 15 minutes). For each step:
    measured_h  hours of the step the device reader ran (samples.interval_s, at most the step)
    ai_wh       AI energy measured in that time: sum of ai_samples.watts x interval_s, in Wh.
                Every row in ai_samples is power drawn on this device, so all of it is on the bill.
    wh          what the model fits: ai_wh, or missing (NaN) when the step is unknown

An agent is ai_samples.app (Claude Code, GitHub Copilot, Ollama, ...): its models and the commands
it runs ("tool runs") are all that agent's energy.

Which steps are unknown (`gaps`):
    "day"      (default) a day the reader ran at least MIN_DAY_HOURS: its steps without readings
               count as no AI use (computer off or asleep), as in the backend's daily totals.
               A day with no readings is unknown.
    "missing"  only steps the reader ran at least MIN_COVERAGE of count, scaled up to the full step;
               every other step is unknown.
    "zero"     every step without readings counts as no AI use.
"""

import pandas as pd

from .config import CONFIG
from .settings import TZ
from .steps import HOUR, STEP, load, per_hour

MIN_COVERAGE = CONFIG["device"]["min_coverage"]
MIN_DAY_HOURS = CONFIG["device"]["min_day_hours"]
GAPS = ("day", "missing", "zero")
OTHER = "Other AI apps"
# An agent gets its own model with this many hours of use and this share of the AI energy;
# smaller ones are forecast together as OTHER. In use: drawing USED_WH an hour (average W) in a step.
USED_WH = CONFIG["agents"]["used_wh"]
MIN_USED_HOURS = CONFIG["agents"]["min_used_hours"]
MIN_SHARE = CONFIG["agents"]["min_share"]
MAX_AGENTS = CONFIG["agents"]["max_agents"]


def _frame(conn, sql, params):
    return pd.DataFrame([dict(r) for r in conn.execute(sql, params).fetchall()])


def _floor(ts, step):
    return pd.to_datetime(ts, unit="s", utc=True).dt.tz_convert(TZ).dt.tz_localize(None).dt.floor(step)


def _scale(measured, gaps):
    """What to multiply a step's measured Wh by to get the modeled value; NaN where unknown.
    measured: hours of each step the reader ran."""
    one = pd.Series(1.0, index=measured.index)
    if gaps == "zero":
        return one
    if gaps == "missing":
        share = measured * per_hour(measured.index)
        return (1 / share).where(share >= MIN_COVERAGE)
    day_hours = measured.groupby(measured.index.date).transform("sum")
    return one.where(day_hours >= MIN_DAY_HOURS)


def ai_energy(conn, device_id, gaps=CONFIG["device"]["gaps"], step=STEP):
    """(energy, by_app): the table above, one row per step (plus `scale`), and measured Wh per step,
    agent and model. step: the length of a step, the configured one unless given."""
    if gaps not in GAPS:
        raise ValueError(f"gaps must be one of {GAPS}")
    empty_apps = pd.DataFrame(columns=["time", "app", "name", "kind", "wh"])
    samples = _frame(conn, "SELECT ts, interval_s FROM samples WHERE device_id = ?", (device_id,))
    if samples.empty:
        return pd.DataFrame(columns=["measured_h", "ai_wh", "scale", "wh"]), empty_apps
    apps = _frame(conn, "SELECT ts, interval_s, watts, kind, app, COALESCE(model, app) AS name "
                        "FROM ai_samples WHERE device_id = ?", (device_id,))
    measured = samples["interval_s"].groupby(_floor(samples["ts"], step)).sum() / 3600
    index = pd.date_range(measured.index.min(), measured.index.max(), freq=step)
    energy = pd.DataFrame(index=index)
    energy["measured_h"] = measured.reindex(index).fillna(0.0).clip(upper=step / HOUR)
    if apps.empty:
        energy["ai_wh"] = 0.0
        by_app = empty_apps
    else:
        apps["time"] = _floor(apps["ts"], step)
        apps["wh"] = apps["watts"].astype(float) * apps["interval_s"].astype(float) / 3600
        energy["ai_wh"] = apps.groupby("time")["wh"].sum().reindex(index).fillna(0.0)
        by_app = apps.groupby(["time", "app", "name", "kind"], as_index=False)["wh"].sum()
    energy["scale"] = _scale(energy["measured_h"], gaps)
    energy["wh"] = energy["ai_wh"] * energy["scale"]
    energy.index.name = "time"
    return energy, by_app


def agent_series(energy, by_app):
    """One column of Wh per step for each AI agent, unknown steps as NaN, biggest agent first. Agents
    with little use or energy are added up in an OTHER column. The columns sum to energy["wh"]."""
    if by_app.empty:
        return pd.DataFrame({OTHER: energy["wh"]})
    wide = (by_app.pivot_table(index="time", columns="app", values="wh", aggfunc="sum")
            .reindex(energy.index).fillna(0.0))
    total = wide.sum().sum()
    n = per_hour(energy.index)
    own = [a for a in wide.sum().sort_values(ascending=False).index
           if (wide[a] * n >= USED_WH).sum() >= MIN_USED_HOURS * n and total > 0 and wide[a].sum() / total >= MIN_SHARE]
    own = own[:MAX_AGENTS]
    out = wide[own].copy()
    rest = wide.drop(columns=own).sum(axis=1)
    if rest.sum() > 0 or not own:
        out[OTHER] = rest
    out = out.mul(energy["scale"], axis=0)
    out.columns.name = None
    return out


def load_energy(path):
    """The table saved by 02_export_readings.py, with a regular index at the configured step."""
    return load(path, "02_export_readings.py")


def load_by_app(path):
    return pd.read_csv(path, parse_dates=["time"])
