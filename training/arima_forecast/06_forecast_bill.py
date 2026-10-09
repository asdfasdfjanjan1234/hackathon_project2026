"""Forecast the electricity bill from the device's fine-tuned per-agent models.

    python 06_forecast_bill.py --device-id 3              through the end of the billing cycle
    python 06_forecast_bill.py --device-id 3 --hours 48

The projected bill is BASELINE_BILL + the AI cost measured so far this cycle + the AI cost forecast
for the hours left, priced by hour on the tariff in backend/.env. Forecasts start at the current
hour; hours since the last reading are bridged by the models. Writes
artifacts/devices/device_<id>_forecast.csv (hour by hour, per agent) and device_<id>_forecast.json.
"""

import argparse
import json

from wattcast import pipeline, readings, settings
from wattcast.config import CONFIG


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-id", type=int, required=True)
    ap.add_argument("--hours", type=int, help="hours to forecast (default: to the end of the billing cycle)")
    ap.add_argument("--paths", type=int, default=CONFIG["forecast"]["paths"], help="simulated futures for the ranges")
    args = ap.parse_args()

    with open(settings.device_artifact(args.device_id, "model.json")) as f:
        saved = json.load(f)
    hourly = readings.load_hourly(settings.device_data(args.device_id, "hourly.csv"))
    agents = readings.agent_series(hourly, readings.load_by_app(settings.device_data(args.device_id, "by_app.csv")))
    table, summary = pipeline.forecast(saved, agents[list(saved["agents"])], hourly, settings.backend_config(),
                                       args.hours, args.paths)

    table.round(5).to_csv(settings.device_artifact(args.device_id, "forecast.csv"))
    with open(settings.device_artifact(args.device_id, "forecast.json"), "w") as f:
        json.dump(summary, f, indent=2)

    b, t = summary["bill"], summary["tariff"]
    print(f"Device {args.device_id}, tariff {t['tariff']}, cycle {b['cycle']['start']} to {b['cycle']['end']}")
    print(f"  Projected bill      P{b['projected_bill']:,.2f}  (P{b['projected_bill_low']:,.2f} - P{b['projected_bill_high']:,.2f})")
    print(f"    baseline          P{b['baseline_bill']:,.2f}")
    print(f"    AI so far         P{b['ai_cost_so_far']:,.2f}  ({b['hours_measured_so_far']} of {b['hours_elapsed']} hours measured)")
    print(f"    AI still to come  P{b['ai_cost_remaining']:,.2f}  (P{b['ai_cost_remaining_low']:,.2f} - P{b['ai_cost_remaining_high']:,.2f})")
    for name, cost in summary["cost_by_agent_rest_of_cycle"].items():
        print(f"      {name:<22} P{cost:,.2f}  [{summary['models'][name]['spec']}]")
    for name, tot in summary["totals"].items():
        print(f"  {name:<34} P{tot['cost']:,.2f}  (P{tot['cost_low']:,.2f} - P{tot['cost_high']:,.2f})  {tot['kwh']} kWh")
    top = table.iloc[:24].sort_values("cost", ascending=False).head(5)
    print("  Costliest hours in the next 24: " + ", ".join(
        f"{h:%a %I %p} P{r.cost:.3f} ({r.level})" for h, r in top.iterrows()))
    if not summary["beats_baselines"]:
        print("  Note: in the backtest a simple baseline did as well as these models; treat the forecast as rough.")
    print(f"-> {settings.device_artifact(args.device_id, 'forecast.csv')} / .json")


if __name__ == "__main__":
    main()
