"""Projects the electricity bill for this billing cycle and the months after it.

For each model, from its daily kWh:
  1. Weekday/weekend pattern: with a week or more of data, weekdays and weekends get
     their own factor (many people use AI less on weekends) and the trend is fitted to
     values with that pattern taken out.
  2. Trend: a least-squares line through the daily values, so growing use gives a
     growing forecast. With fewer than MIN_TREND_DAYS days there's no trend, just the average.
  3. Projection: the trend carries on but levels off (damped by DAMPING per day), so a
     12-month projection doesn't grow without limit.

Days the device reader didn't run aren't zeros: they're left out of the fit and projected.
Only energy used on this device is on the bill; cloud data-center energy isn't.

When the device has a fine-tuned ARIMA that's in use (arima_forecast.py), the rest of this cycle
comes from it instead, with a range; the months after it stay on the trend.
"""

import calendar
from collections import defaultdict
from datetime import date, timedelta

DAMPING = 0.99         # share of the daily trend that carries over to the next day
MIN_TREND_DAYS = 3     # fewer days than this: project the average, no trend
MIN_WEEKLY_DAYS = 7    # a weekday/weekend pattern needs at least a week
HORIZONS = (1, 3, 12)  # months projected after this cycle


def billing_cycle(today, start_day=1):
    """(first day, last day) of the billing cycle containing `today`, with the meter read on `start_day`."""
    def start_in(year, month):
        return date(year, month, min(max(start_day, 1), calendar.monthrange(year, month)[1]))

    start = start_in(today.year, today.month)
    if today < start:
        start = start_in(*((today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)))
    nxt = start_in(*((start.year, start.month + 1) if start.month < 12 else (start.year + 1, 1)))
    return start, nxt - timedelta(days=1)


def _linear_trend(xs, ys):
    """Least-squares slope and intercept."""
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / den if den else 0.0
    return slope, mean_y - slope * mean_x


def _is_weekend(day):
    return day.weekday() >= 5


class Trend:
    """Daily kWh of one model: weekday/weekend factors and a damped linear trend."""

    def __init__(self, points):
        """points: [(date, kWh)] for the days that were measured, oldest first."""
        values = [v for _, v in points]
        mean = sum(values) / len(values)
        self.factors = {False: 1.0, True: 1.0}
        if len(points) >= MIN_WEEKLY_DAYS and mean > 0:
            weekday = [v for d, v in points if not _is_weekend(d)]
            weekend = [v for d, v in points if _is_weekend(d)]
            if weekday and weekend:
                self.factors = {False: sum(weekday) / len(weekday) / mean, True: sum(weekend) / len(weekend) / mean}
        self.first, self.last = points[0][0], points[-1][0]
        xs = [(d - self.first).days for d, _ in points]
        ys = [v / (self.factors[_is_weekend(d)] or 1.0) for d, v in points]
        if len(points) >= MIN_TREND_DAYS and xs[-1] > 0:
            self.slope, self.intercept = _linear_trend(xs, ys)
        else:
            self.slope, self.intercept = 0.0, sum(ys) / len(ys)
        self.weekly = self.factors != {False: 1.0, True: 1.0}

    def predict(self, day):
        x_last = (self.last - self.first).days
        ahead = (day - self.last).days
        if ahead <= 0:  # inside the measured range; before it, hold the first level
            level = self.intercept + self.slope * max((day - self.first).days, 0)
        else:
            growth = DAMPING * (1 - DAMPING ** ahead) / (1 - DAMPING)
            level = self.intercept + self.slope * (x_last + growth)
        return max(0.0, level) * self.factors[_is_weekend(day)]


def _parse(day):
    return day if isinstance(day, date) else date.fromisoformat(str(day)[:10])


def _days(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def forecast_bill(daily, rate, baseline_bill, today=None, cycle_start_day=1, measured_days=None,
                  reductions=None, budget=None, ahead=None):
    """Bill forecast for the billing cycle containing `today`, plus HORIZONS months after it.

    measured_days: [{date, hours}] the device reader ran (None: every day
    from the first to the last row counts). reductions: {model: fraction of its energy the
    recommendations save}, used for the "with recommendations" path from tomorrow on.
    ahead: the ARIMA forecast (arima_forecast.arima_ahead): {"days": {date: AI kWh still to come},
    "low", "high"}. It replaces the trend from now to the end of the cycle: today is what was
    measured plus the rest of the day. The recommendations save the share they save of the trend's
    day, and the per-model figures are the trend's, scaled to the ARIMA total.
    """
    today = today or date.today()
    reductions = reductions or {}
    start, end = billing_cycle(today, cycle_start_day)
    cycle_days = _days(start, end)

    kwh, kinds = defaultdict(lambda: defaultdict(float)), {}
    for row in daily:
        # Only energy used on this device is on the bill; cloud data-center energy isn't.
        if row.get("source", "measured") != "measured":
            continue
        kwh[row["model"]][_parse(row["date"])] += row["kwh"]
        kinds[row["model"]] = row.get("kind", "local")

    if measured_days is not None:
        observed = {_parse(d["date"]) for d in measured_days}
        hours = sum(d.get("hours", 0) for d in measured_days)
    else:
        dated = [d for m in kwh.values() for d in m]
        observed = set(_days(min(dated), max(dated))) if dated else set()
        hours = 24.0 * len(observed)
    observed = {d for d in observed if d <= today}
    past = sorted(d for d in observed if d < today)

    trends = {}
    for model, by_day in kwh.items():
        # Today is still in progress, so it's only fitted when there's nothing else to go on.
        fit_days = past if any(by_day.get(d) for d in past) else sorted(observed)
        if fit_days:
            trends[model] = Trend([(d, by_day.get(d, 0.0)) for d in fit_days])

    def day_kwh(model, day):
        """(kWh, measured?) for one model on one day of the cycle."""
        t, actual = trends[model], kwh[model].get(day, 0.0)
        if day in observed and day < today:
            return actual, True
        if day == today and day in observed:
            return max(actual, t.predict(day)), True
        return t.predict(day), False

    series, cum, cum_recs = [], 0.0, 0.0
    by_model_kwh, remaining_kwh = defaultdict(float), defaultdict(float)
    cycle_kwh = left_kwh = 0.0  # AI energy this cycle, and after today
    base_per_day = baseline_bill / len(cycle_days)
    exceeded = exceeded_recs = None
    for day in cycle_days:
        ai = ai_recs = 0.0
        measured = day in observed
        for model in trends:
            value, _ = day_kwh(model, day)
            by_model_kwh[model] += value
            if day > today:
                remaining_kwh[model] += value
            ai += value
            ai_recs += value * (1 - reductions.get(model, 0.0)) if day > today else value
        if ahead is not None and day == today:
            ai = ai_recs = sum(kwh[m].get(day, 0.0) for m in kwh) + ahead["days"].get(day, 0.0)
        elif ahead is not None and day > today:
            kept = ai_recs / ai if ai > 0 else 1.0
            ai = ahead["days"].get(day, 0.0)
            ai_recs = ai * kept
        cycle_kwh += ai
        if day > today:
            left_kwh += ai
        cum += base_per_day + ai * rate
        cum_recs += base_per_day + ai_recs * rate
        if budget is not None and exceeded is None and cum > budget:
            exceeded = day
        if budget is not None and exceeded_recs is None and cum_recs > budget:
            exceeded_recs = day
        series.append({
            "date": day.isoformat(), "is_past": day < today, "is_today": day == today, "measured": measured,
            "ai_kwh": round(ai, 4), "ai_cost": round(ai * rate, 2),
            "baseline_to_date": round(base_per_day * (len(series) + 1), 2),
            "bill_to_date": round(cum, 2), "bill_to_date_with_recommendations": round(cum_recs, 2),
        })

    # With the ARIMA forecast, each model keeps its share of the trend's total.
    month_scale = cycle_kwh / sum(by_model_kwh.values()) if sum(by_model_kwh.values()) > 0 else 1.0
    left_scale = left_kwh / sum(remaining_kwh.values()) if sum(remaining_kwh.values()) > 0 else 1.0
    models = []
    for model, total in by_model_kwh.items():
        t = trends[model]
        total, left = total * month_scale, remaining_kwh[model] * left_scale
        models.append({
            "model": model,
            "kind": kinds.get(model, "local"),
            "monthly_kwh": round(total, 4),
            "monthly_cost": round(total * rate, 2),
            "remaining_cost": round(left * rate, 2),  # rest of the cycle, after today
            "daily_trend_kwh": round(t.slope, 5),
            "avg_daily_kwh": round(total / len(cycle_days), 5),
            "weekly_pattern": t.weekly,
        })
    ai_cost = cycle_kwh * rate
    ai_cost_recs = cum_recs - baseline_bill
    forecast_range = None
    if ahead is not None:  # the range is the ARIMA's, of the AI energy still to come
        to_come = sum(v for d, v in ahead["days"].items() if today <= d <= end) * rate
        forecast_range = {"low": round(baseline_bill + ai_cost - to_come * (1 - ahead["low"]), 2),
                          "high": round(baseline_bill + ai_cost + to_come * (ahead["high"] - 1), 2)}

    return {
        "month": start.strftime("%Y-%m"),
        "cycle": {"start": start.isoformat(), "end": end.isoformat(), "days": len(cycle_days),
                  "start_day": cycle_start_day},
        "days_left": (end - today).days + 1,
        "baseline_bill": baseline_bill,
        "ai_cost": round(ai_cost, 2),
        "forecast_bill": round(baseline_bill + ai_cost, 2),
        "forecast_range": forecast_range,
        "ai_cost_with_recommendations": round(ai_cost_recs, 2),
        "forecast_bill_with_recommendations": round(cum_recs, 2),
        "by_model": sorted(models, key=lambda m: m["monthly_cost"], reverse=True),
        "daily": series,
        "projections": _projections(trends, end, cycle_start_day, rate, baseline_bill, reductions),
        "budget": budget,
        "budget_exceeded_on": exceeded and exceeded.isoformat(),
        "budget_exceeded_on_with_recommendations": exceeded_recs and exceeded_recs.isoformat(),
        "coverage": {"days_measured": len(observed), "hours_measured": round(hours, 2),
                     "first": min(observed).isoformat() if observed else None,
                     "last": max(observed).isoformat() if observed else None},
    }


def _projections(trends, cycle_end, cycle_start_day, rate, baseline_bill, reductions):
    """Bills for the next 1, 3 and 12 billing cycles, on the current path and with recommendations."""
    cycles, end = [], cycle_end
    for _ in range(max(HORIZONS)):
        start, end = billing_cycle(end + timedelta(days=1), cycle_start_day)
        kwh = kwh_recs = 0.0
        for day in _days(start, end):
            for model, t in trends.items():
                value = t.predict(day)
                kwh += value
                kwh_recs += value * (1 - reductions.get(model, 0.0))
        cycles.append((kwh, kwh_recs))
    out = []
    for months in HORIZONS:
        kwh, kwh_recs = (sum(c[i] for c in cycles[:months]) for i in (0, 1))
        bill, bill_recs = months * baseline_bill + kwh * rate, months * baseline_bill + kwh_recs * rate
        out.append({"months": months, "ai_kwh": round(kwh, 2), "ai_cost": round(kwh * rate, 2),
                    "bill": round(bill, 2), "bill_with_recommendations": round(bill_recs, 2),
                    "monthly_bill": round(bill / months, 2),
                    "monthly_bill_with_recommendations": round(bill_recs / months, 2)})
    return out
