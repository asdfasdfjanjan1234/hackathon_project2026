"""Checks our whole-machine readings against a wall meter (a plug-in power meter or smart plug).

Two kinds of check:
  watts  type in what the meter shows now; it's compared with our average over the last
         SPOT_WINDOW_S seconds, so hold the load steady while reading the meter
  kwh    note the meter's kWh counter, run any workload, note it again; it's compared
         with the energy we recorded in between. Meters count in 0.01 kWh steps, so a
         laptop needs an hour or more for a useful check; a gaming PC a few minutes.

The meter reads at the wall, so it also counts the charger's losses (often 5-15%) and any
battery charging: keep a laptop at 100% while checking. Differences are shown as they are,
without correcting for either.
"""

import time

from . import storage

SPOT_WINDOW_S = 30
MIN_COVERAGE = 0.9   # a kWh check needs the device reader running this share of the window
MAX_SAMPLE_AGE_S = 15


class CheckError(ValueError):
    """The check can't be taken; the message says why."""


def _difference(app_value, meter_value):
    if app_value is None or not meter_value:
        return None
    return round((app_value - meter_value) / meter_value * 100, 1)


def describe(check):
    """A stored check with its readings in plain terms and the difference from the meter."""
    open_ = check["ended_at"] is None
    if check["kind"] == "watts":
        meter = check["meter_end"]
    else:
        meter = None if open_ else check["meter_end"] - check["meter_start"]
    return {
        "id": check["id"], "kind": check["kind"], "open": open_,
        "started_at": check["started_at"], "ended_at": check["ended_at"],
        "minutes": None if open_ else round((check["ended_at"] - check["started_at"]) / 60, 1),
        "meter": meter, "meter_start": check["meter_start"], "app": check["app_value"], "coverage": check["coverage"],
        "difference_pct": None if open_ else _difference(check["app_value"], meter),
        "unit": "W" if check["kind"] == "watts" else "kWh",
    }


def summary(checks):
    """Average absolute difference over the finished checks: the accuracy figure for the pitch."""
    done = [c for c in checks if c["difference_pct"] is not None]
    if not done:
        return {"checks": 0, "mean_abs_difference_pct": None, "worst_pct": None}
    diffs = [abs(c["difference_pct"]) for c in done]
    return {"checks": len(done), "mean_abs_difference_pct": round(sum(diffs) / len(diffs), 1),
            "worst_pct": max(diffs)}


def spot_check(conn, device_id, meter_watts, now=None):
    now = now or time.time()
    if meter_watts is None or meter_watts <= 0:
        raise CheckError("Enter the watts the meter shows.")
    ours = storage.machine_energy(conn, now - SPOT_WINDOW_S, now, device_id)
    latest = storage.latest_sample(conn, max_age_s=MAX_SAMPLE_AGE_S)
    if not latest or ours["avg_watts"] is None:
        raise CheckError("No recent readings: start the device reader first.")
    if ours["coverage"] < MIN_COVERAGE:
        raise CheckError(f"The device reader needs {SPOT_WINDOW_S} s of readings first: try again in a moment.")
    return storage.add_meter_check(conn, "watts", now, now, meter_end=meter_watts,
                                   app_value=round(ours["avg_watts"], 2), coverage=round(ours["coverage"], 3),
                                   device_id=device_id)


def open_check(checks):
    return next((c for c in checks if c["kind"] == "kwh" and c["ended_at"] is None), None)


def start_window(conn, device_id, meter_kwh, now=None):
    if meter_kwh is None or meter_kwh < 0:
        raise CheckError("Enter the meter's kWh counter.")
    if open_check(storage.meter_checks(conn, device_id)):
        raise CheckError("A kWh check is already running: finish it first.")
    return storage.add_meter_check(conn, "kwh", now or time.time(), meter_start=meter_kwh, device_id=device_id)


def finish_window(conn, device_id, meter_kwh, now=None):
    now = now or time.time()
    check = open_check(storage.meter_checks(conn, device_id))
    if not check:
        raise CheckError("No kWh check is running.")
    if meter_kwh is None or meter_kwh < check["meter_start"]:
        raise CheckError("The end reading must be at least the start reading.")
    ours = storage.machine_energy(conn, check["started_at"], now, device_id)
    if ours["coverage"] < MIN_COVERAGE:
        storage.delete_meter_check(conn, check["id"])
        raise CheckError(f"The device reader ran for only {ours['coverage']:.0%} of the check, so it was "
                         f"discarded. Keep it running for the whole check.")
    storage.finish_meter_check(conn, check["id"], now, meter_kwh, round(ours["kwh"], 6), round(ours["coverage"], 3))
    return check["id"]
