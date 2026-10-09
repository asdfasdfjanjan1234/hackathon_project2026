"""Fine-tune: one ARIMA per AI agent on a device, built on when and how heavily that agent is used.

For each agent (Claude Code, GitHub Copilot, Ollama, ...; small ones together as "Other AI apps"):
    - its weekly routine is learned from its own hours (typical level per hour of the week)
    - candidates are fitted on the hours before the held-out days: the routine alone, and each of
      the --top Luzon structures started from the Luzon coefficients (warm) and from scratch (cold)
    - the one that forecasts the held-out days best is refitted on all the agent's hours
The agents' held-out forecasts are added up and compared with simple baselines on the device's total
AI energy. Saved to artifacts/devices/device_<id>_model.json.

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

from wattcast import pipeline, readings, settings
from wattcast.config import CONFIG


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-id", type=int, required=True)
    ap.add_argument("--folds", type=int, default=CONFIG["device"]["folds"], help="held-out days, at most")
    ap.add_argument("--top", type=int, default=CONFIG["device"]["top_structures"],
                    help="Luzon model structures to try per agent")
    ap.add_argument("--fresh", action="store_true", help="ignore checkpoints and fit everything again")
    ap.add_argument("--show-iterations", action="store_true",
                    help="print the log-likelihood after every optimizer iteration of every fit")
    args = ap.parse_args()
    if args.show_iterations:
        CONFIG["model"]["show_iterations"] = True

    hourly = readings.load_hourly(settings.device_data(args.device_id, "hourly.csv"))
    agents = readings.agent_series(hourly, readings.load_by_app(settings.device_data(args.device_id, "by_app.csv")))
    luzon = pipeline.load_luzon()
    if luzon[0][1] is None:
        print("No Luzon model yet (run 04_pretrain_luzon.py): fitting from scratch only.")
    print(f"Device {args.device_id}: {hourly['wh'].notna().sum()} known hours, {hourly.index[0]} to "
          f"{hourly.index[-1]}; agents: {', '.join(agents.columns)}")
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
    if not saved["beats_baselines"]:
        print("  Note: a simple baseline forecast the held-out days at least as well. Collect more days "
              "of readings before relying on the ARIMA forecast.")


if __name__ == "__main__":
    main()
