from flask import Blueprint, current_app, request

api_bp = Blueprint("api", __name__)


def bill_params():
    """The user's rate, bills and budget: query parameters override the .env defaults."""
    cfg = current_app.config

    def arg(name, key):
        return request.args.get(name, type=float, default=cfg[key])

    rate = arg("rate", "ELECTRICITY_RATE")
    return {
        "rate": rate,
        "baseline_bill": arg("baseline_bill", "BASELINE_BILL"),
        "current_bill": arg("current_bill", "CURRENT_BILL"),
        "baseline_rate": request.args.get("baseline_rate", type=float, default=cfg["BASELINE_RATE"]),
        "budget": arg("budget", "MONTHLY_BUDGET"),
        "cycle_start_day": min(max(request.args.get("cycle_start_day", type=int,
                                                    default=cfg["BILLING_CYCLE_START_DAY"]), 1), 31),
    }


from . import device, forecast, health, impact, live, models, readings, recommendations, system, usage  # noqa: E402,F401
