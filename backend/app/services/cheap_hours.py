"""Cheapest hours to run heavy AI jobs, from the user's tariff, and the best hours for price and CO2 together.

Philippine households pay one rate at every hour unless they're on Meralco's Peak/Off-Peak (POP)
program, so there's no live hourly price to fetch: the spot market (WESM, run by IEMOP) moves every
5 minutes, but households only see it as a monthly average, and IEMOP's data feed is a paid
subscription. What does change by the hour is POP's fixed schedule (meralco.com.ph, Oct 2026):

  peak      Mon-Sat 8 AM - 9 PM, Sun 6 PM - 8 PM
  off-peak  every other hour: Mon-Sat 9 PM - 8 AM, most of Sunday
  rates     off-peak generation P3.55/kWh vs P5.69 on the regular rate (P2.14 less); peak generation
            P7.28 in the wet season, P7.49 in the dry (about P1.59-1.80 more). Both move with the
            monthly generation charge adjustment, so set POP_PEAK_RATE / POP_OFFPEAK_RATE from a bill.

  flat      shifting doesn't change the bill. We show what POP would cost for the same AI use, and
            whether the household qualifies (POP needs an average of 500 kWh a month).
  pop       SHIFTABLE_SHARE of AI energy in peak hours (batch work that can wait) moves off-peak.

Use is by hour of day, averaged over all days, so an hour's peak share is the days of the week it's
peak (8 AM is peak 6 days of 7). Holidays aren't modelled. The best window is the cleanest
off-peak window on POP, and simply the cleanest window on a flat rate.
"""

from datetime import datetime, timedelta

from .clean_hours import SHIFTABLE_SHARE, _hour_label, _window

OFFPEAK_DISCOUNT = 2.14  # P/kWh off-peak is below the regular rate
PEAK_PREMIUM = 1.59      # P/kWh peak is above it (wet season; about 1.80 in the dry season)
POP_MIN_KWH = 500        # average kWh a month to join POP
OFFPEAK_LABEL = "9 PM – 8 AM Mon–Sat, all Sunday except 6–8 PM"


def is_peak(weekday, hour):
    """weekday: 0 Monday ... 6 Sunday."""
    return 18 <= hour < 20 if weekday == 6 else 8 <= hour < 21


def peak_share(hour):
    """Share of the week's days on which this hour of day is a peak hour."""
    return sum(is_peak(d, hour) for d in range(7)) / 7


def pop_rates(rate, peak_rate=0.0, offpeak_rate=0.0):
    """(peak, off-peak) P/kWh: the ones given, else estimated from the regular rate."""
    return (round(peak_rate or rate + PEAK_PREMIUM, 4),
            round(offpeak_rate or max(rate - OFFPEAK_DISCOUNT, 0.0), 4))


def _pop_cost(kwh_by_hour, peak, off):
    return sum(kwh * (peak_share(h) * peak + (1 - peak_share(h)) * off) for h, kwh in kwh_by_hour.items())


def _next_change(now, tariff_peak):
    """The time the tariff next switches between peak and off-peak, as "9 PM" or "Mon 8 AM"."""
    t = now.replace(minute=0, second=0, microsecond=0)
    for _ in range(48):
        t += timedelta(hours=1)
        if is_peak(t.weekday(), t.hour) != tariff_peak:
            return _hour_label(t.hour) if t.date() == now.date() else f"{t:%a} {_hour_label(t.hour)}"
    return None


def _best(tariff, clean, window_hours):
    """The best window to run batch AI: the cleanest off-peak window on POP, the cleanest one on a flat rate."""
    intensity = {p["hour"]: p["g_per_kwh"] for p in (clean or {}).get("intensity") or [] if p["g_per_kwh"] is not None}
    plan = (clean or {}).get("plan")
    if tariff == "flat":
        if not plan:
            return None
        return {**plan["cleanest"], "reason": "Your rate is the same every hour, so this is just the cleanest window."}
    # Off-peak Monday to Saturday; Sunday's off-peak hours are a superset.
    windows = [(sum(intensity[h] for h in _window(s, window_hours)) / window_hours, s) for s in range(24)
               if all(h in intensity and not is_peak(0, h) for h in _window(s, window_hours))]
    if not windows:
        return {"start_hour": 21, "end_hour": 8, "g_per_kwh": None, "label": "9 PM – 8 AM",
                "reason": "Off-peak hours. Connect hourly grid data to also pick the cleanest of them."}
    g, s = min(windows)
    note = ""
    if plan and plan["cleanest"]["g_per_kwh"] < g:
        note = (f" The grid is cleaner {plan['cleanest']['label']} ({plan['cleanest']['g_per_kwh']:,.0f} g), "
                f"but that's peak.")
    return {"start_hour": s, "end_hour": (s + window_hours) % 24, "g_per_kwh": round(g, 1),
            "label": f"{_hour_label(s)} – {_hour_label(s + window_hours)}",
            "reason": f"Off-peak, and the cleanest off-peak hours on the grid.{note}"}


def cheap_hours(use_by_hour, params, clean=None, window_hours=3, now=None):
    """Everything the "best time to run AI" card and the "cheap hours" recommendation need.

    use_by_hour: {hour: average AI kWh a day}. params: bill_params() (rate, tariff, peak_rate,
    offpeak_rate, current_bill). clean: clean_hours() output, for the CO2 side.
    """
    now = now or datetime.now().astimezone()
    rate, tariff = params["rate"], params.get("tariff", "flat")
    peak, off = pop_rates(rate, params.get("peak_rate", 0.0), params.get("offpeak_rate", 0.0))
    month = {h: kwh * 30 for h, kwh in use_by_hour.items() if kwh > 0}
    kwh_month = sum(month.values())
    peak_kwh = sum(kwh * peak_share(h) for h, kwh in month.items())
    flat_cost = kwh_month * rate
    pop_cost = _pop_cost(month, peak, off)
    moved = peak_kwh * SHIFTABLE_SHARE
    shift_saves = moved * (peak - off)

    def hour_rate(h, day=now.weekday()):
        return rate if tariff == "flat" else peak if is_peak(day, h) else off

    peak_now = is_peak(now.weekday(), now.hour)
    info = {
        "tariff": tariff, "rate": rate, "peak_rate": peak, "offpeak_rate": off, "offpeak_label": OFFPEAK_LABEL,
        # Today's schedule. On a flat rate `peak` marks the hours POP would charge more for.
        "schedule": [{"hour": h, "peak": is_peak(now.weekday(), h), "rate": hour_rate(h)} for h in range(24)],
        "now": {"rate": hour_rate(now.hour), "peak": peak_now if tariff == "pop" else None,
                "changes_at": _next_change(now, peak_now) if tariff == "pop" else None},
        "ai": {"kwh_month": round(kwh_month, 4), "peak_share": round(peak_kwh / kwh_month, 3) if kwh_month else None,
               "cost_month": round(pop_cost if tariff == "pop" else flat_cost, 2)},
        "shift": None, "what_if_pop": None,
        "best": _best(tariff, clean, window_hours),
    }
    if tariff == "pop" and shift_saves > 0:
        info["shift"] = {"share": SHIFTABLE_SHARE, "kwh_month": round(moved, 4), "savings": round(shift_saves, 2)}
    if tariff == "flat":
        household = params.get("current_bill", 0.0) / rate if rate else 0.0
        info["what_if_pop"] = {
            "cost_month_flat": round(flat_cost, 2), "cost_month_pop": round(pop_cost, 2),
            "cost_month_pop_shifted": round(pop_cost - shift_saves, 2),
            "household_kwh_month": round(household), "min_kwh": POP_MIN_KWH, "eligible": household >= POP_MIN_KWH,
        }
    return info


def cheap_hours_rec(info):
    """The "cheap hours" recommendation on POP, or None on a flat rate or with no AI use in peak hours."""
    s = info and info.get("shift")
    if not s:
        return None
    best = info["best"]
    when = f" The best of them is {best['label']}: {best['reason'][0].lower()}{best['reason'][1:]}" if best else ""
    return {
        "action": "SWITCH", "rule": "cheap hours", "model": "All AI workloads",
        "message": (f"{info['ai']['peak_share']:.0%} of your AI energy runs in peak hours (₱{info['peak_rate']:,.2f}/kWh). "
                    f"Running batch jobs (evals, indexing, long agent runs) off-peak at ₱{info['offpeak_rate']:,.2f}/kWh "
                    f"({OFFPEAK_LABEL}) saves about ₱{s['savings']:,.2f} a month.{when}"),
        "monthly_savings": s["savings"], "scope": "bill", "alternative": False, "window": best,
    }
