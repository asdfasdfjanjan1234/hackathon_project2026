"""Fine-tune: one ARIMA per AI agent on a device, built on when and how heavily that agent is used.

The readings are in steps of step_minutes (config.json; 15 minutes), so a device can be fine-tuned
on a few hours of them: device.min_hours known hours, with the last device.folds windows of
device.horizon_hours held out and at least device.min_train_hours before them to fit on.

For each agent (Claude Code, GitHub Copilot, Ollama, ...; small ones together as "Other AI apps"):
    - its weekly routine is learned from its own readings (typical level per hour of the week)
    - candidates are fitted on the steps before the held-out windows: the routine alone, and each
      of the --top Luzon structures started from the Luzon coefficients (warm) and from scratch
      (cold). A structure with a one-day season is tried once there are two days to fit on.
    - the one that forecasts the held-out windows best is refitted on all the agent's steps
The agents' held-out forecasts are added up and compared with simple baselines on the device's total
AI energy. Saved to artifacts/devices/device_<id>_model.json.

Hours of the day the device hasn't been read in yet are forecast at its average level: after an
evening of readings the forecast doesn't know the mornings. It learns them as they're read.

Every fit is checkpointed in artifacts/devices/device_<id>_checkpoints, so an interrupted run
resumes where it stopped; --fresh fits everything again. Settings come from config.json.

ARIMA has no epochs: each fit is one optimization, and the log shows how many iterations it took
(at most model.maxiter). --show-iterations prints the log-likelihood after every iteration.

    python 05_finetune_device.py --device-id 3
    python 05_finetune_device.py --device-id 3 --fresh
    python 05_finetune_device.py --device-id 3 --show-iterations
"""

import argparse
import json
import sys

from wattcast import pipeline, readings, settings, steps
from wattcast.config import CONFIG


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-id", type=int, required=True)
    ap.add_argument("--folds", type=int, default=CONFIG["device"]["folds"], help="held-out windows, at most")
    ap.add_argument("--top", type=int, default=CONFIG["device"]["top_structures"],
                    help="Luzon model structures to try per agent")
    ap.add_argument("--fresh", action="store_true", help="ignore checkpoints and fit everything again")
    ap.add_argument("--show-iterations", action="store_true",
                    help="print the log-likelihood after every optimizer iteration of every fit")
    args = ap.parse_args()
    if args.show_iterations:
        CONFIG["model"]["show_iterations"] = True

    try:
        energy = readings.load_energy(settings.device_data(args.device_id, "energy.csv"))
        agents = readings.agent_series(energy, readings.load_by_app(settings.device_data(args.device_id, "by_app.csv")))
        luzon = pipeline.load_luzon()
    except (FileNotFoundError, ValueError) as e:
        sys.exit(str(e))
    if luzon[0][1] is None:
        print("No Luzon model yet (run 04_pretrain_luzon.py): fitting from scratch only.")
    print(f"Device {args.device_id}: {steps.hours(int(energy['wh'].notna().sum()), energy.index):g} known hours in "
          f"{steps.MINUTES}-minute steps, {energy.index[0]} to {energy.index[-1]}; agents: {', '.join(agents.columns)}")
    try:
        saved = pipeline.finetune(agents, args.device_id, luzon, args.folds, args.top,
                                  ckpt=pipeline.device_checkpoints(args.device_id, fresh=args.fresh),
                                  bill_cfg=settings.backend_config())
    except ValueError as e:
        sys.exit(f"Device {args.device_id}: {e}")
    path = settings.device_artifact(args.device_id, "model.json")
    with open(path, "w") as f:
        json.dump(saved, f, indent=2)
    run = saved["run"]
    print(f"{run['checkpoints']['fitted']} fitted, {run['checkpoints']['from_checkpoint']} from checkpoints, "
          f"{run['seconds']:.0f}s; checkpoints and config in {run['checkpoints']['folder']}")
    if run["not_converged"]:
        print(f"  {len(run['not_converged'])} fit(s) stopped at the iteration cap without converging: "
              + "; ".join(run["not_converged"]))
        print("  Raise model.maxiter in config.json and run again (only those are refitted).")
    print(f"-> {path}")
    if saved["coverage"]["hours_of_day"] < 24:
        print(f"  Note: the readings cover {saved['coverage']['hours_of_day']} of the 24 hours of the day. The "
              "others are forecast at this device's average level until they've been read.")
    if not saved["beats_baselines"]:
        print("  Note: a simple baseline forecast the held-out windows at least as well. Collect more "
              "readings before relying on the ARIMA forecast.")


if __name__ == "__main__":
    main()
