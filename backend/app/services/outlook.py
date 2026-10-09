"""The bill forecast and the recommendations together, since each needs the other:
recommendations come from the forecast, and the "with recommendations" path of the
forecast applies their savings.

snapshot() gathers what the dashboard's views show into one reading, for the alerts and
for the assistant's facts."""

from contextlib import closing

from flask import current_app

from . import storage
from .carbon import carbon_report, with_carbon
from .cheap_hours import cheap_hours
from .forecasting import forecast_bill
from .measurement import read_live_power
from .model_usage import model_usage
from .recommendations import build_recommendations, reductions
from .usage_store import (get_clean_hours, get_daily_usage, get_hourly_usage, get_signals, summarize_by_model,
                          usage_window)


def outlook(params, today=None):
    daily, signals = get_daily_usage(), get_signals()
    # The tariff comes with the request (settings), so cheap hours is worked out here, not in get_signals.
    signals["cheap_hours"] = cheap_hours(signals["hourly_use"], params, signals["clean_hours"],
                                         current_app.config["CLEAN_WINDOW_HOURS"])
    common = dict(rate=params["rate"], baseline_bill=params["baseline_bill"], today=today,
                  cycle_start_day=params["cycle_start_day"], measured_days=signals.get("measured_days"),
                  budget=params["budget"])
    forecast = forecast_bill(daily, **common)
    recs = build_recommendations(daily, forecast, params["rate"], params["budget"], signals, today)
    saved = reductions(recs, forecast)
    forecast = forecast_bill(daily, **common, reductions=saved)
    forecast["monthly_savings"] = round(sum(m["monthly_cost"] * saved.get(m["model"], 0.0)
                                            for m in forecast["by_model"]), 2)
    return forecast, recs


def carbon_outlook(params, forecast, recs, window_id="30d"):
    """The carbon report for a 7D, 30D or MTD window. `recs` carry their CO₂ savings (with_carbon)."""
    cfg = current_app.config
    window = usage_window(window_id)
    window.pop("since_ts")

    def in_window(r):
        return window["start"] <= r["date"] <= window["end"]

    return carbon_report(
        [r for r in get_daily_usage(days=32) if in_window(r)],
        [r for r in model_usage(days=32)["daily"] if in_window(r)],
        forecast, recs, window,
        rate=params["rate"], grid=cfg["GRID_CO2_KG_PER_KWH"], datacenter=cfg["DATACENTER_CO2_KG_PER_KWH"],
        budget_kg=params["carbon_budget"],
    )


def snapshot(params, window_id="30d"):
    """One reading of everything the dashboard shows: the live power, the bill forecast, the
    recommendations, usage and carbon in the selected window, and the tariff."""
    cfg = current_app.config
    forecast, recs = outlook(params)
    recs = with_carbon(recs, params["rate"], cfg["GRID_CO2_KG_PER_KWH"], cfg["DATACENTER_CO2_KG_PER_KWH"])
    carbon = carbon_outlook(params, forecast, recs, window_id)
    window = carbon["window"]
    daily = [r for r in get_daily_usage(days=32) if window["start"] <= r["date"] <= window["end"]]
    with closing(storage.connect(cfg["DATABASE"])) as conn:
        live = storage.latest_sample(conn) or read_live_power()
    hourly = get_hourly_usage()
    clean = get_clean_hours(hourly)
    return {"params": params, "live": live, "forecast": forecast, "recommendations": recs, "carbon": carbon,
            "usage": summarize_by_model(daily, params["rate"]), "window": window, "clean": clean,
            "tariff": cheap_hours(hourly, params, clean, cfg["CLEAN_WINDOW_HOURS"]),
            "grid_co2_kg_per_kwh": cfg["GRID_CO2_KG_PER_KWH"]}
