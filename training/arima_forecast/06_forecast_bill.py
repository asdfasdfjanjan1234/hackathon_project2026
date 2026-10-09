"""Forecast the electricity bill from the device's fine-tuned per-agent models.

    python 06_forecast_bill.py --device-id 3              through the end of the billing cycle
    python 06_forecast_bill.py --device-id 3 --hours 48

The projected bill is BASELINE_BILL + the AI cost measured so far this cycle + the AI cost forecast
for the time left, priced by hour on the tariff in backend/.env. Forecasts are in steps of
step_minutes (config.json) and start at the current step; steps since the last reading are bridged
by the models. Writes artifacts/devices/device_<id>_forecast.csv (step by step, per agent) and
device_<id>_forecast.json.
"""

import argparse
import json
import os
import sys

from wattcast import pipeline, readings, settings, steps
from wattcast.config import CONFIG


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-id", type=int, required=True)
    ap.add_argument("--hours", type=int, help="hours to forecast (default: to the end of the billing cycle)")
    ap.add_argument("--paths", type=int, default=CONFIG["forecast"]["paths"], help="simulated futures for the ranges")
    args = ap.parse_args()

    path = settings.device_artifact(args.device_id, "model.json")
    if not os.path.exists(path):
        sys.exit(f"{path} not found: run 05_finetune_device.py --device-id {args.device_id} first")
    with open(path) as f:
        saved = json.load(f)
    try:
        energy = readings.load_energy(settings.device_data(args.device_id, "energy.csv"))
        agents = readings.agent_series(energy, readings.load_by_app(settings.device_data(args.device_id, "by_app.csv")))
        table, summary = pipeline.forecast(saved, agents[list(saved["agents"])], energy, settings.backend_config(),
                                           args.hours, args.paths)
    except (FileNotFoundError, ValueError) as e:
        sys.exit(f"Device {args.device_id}: {e}")

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
    day = table["cost"].iloc[:steps.count(24, table.index)]
    top = day.groupby(day.index.floor("h")).sum().sort_values(ascending=False).head(5)
    print("  Costliest hours in the next 24: " + ", ".join(f"{h:%a %I %p} P{cost:.3f}" for h, cost in top.items()))
    seen = (summary["coverage"] or {}).get("hours_of_day", 24)
    if seen < 24:
        print(f"  Note: the model has read {seen} of the 24 hours of the day; the others are forecast at this "
              "device's average level.")
    if not summary["beats_baselines"]:
        print("  Note: in the backtest a simple baseline did as well as these models; treat the forecast as rough.")
    print(f"-> {settings.device_artifact(args.device_id, 'forecast.csv')} / .json")


if __name__ == "__main__":
    main()
