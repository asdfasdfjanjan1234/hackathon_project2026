"""Pre-train: rank the ARIMA structures by how well they forecast Luzon's demand, and save them.

The demand is in steps of step_minutes (config.json; 15 minutes). Each candidate (model.CANDIDATES)
is fitted on the steps before the last --folds days, then scored on forecasting each of those days
24 hours ahead (backtest.py). The best by held-out MASE is refitted on all the data and saved, with
the whole comparison, to artifacts/luzon/luzon_pretrained.json. Devices start from it in
05_finetune_device.py: the structures without a season from their first hours of readings, the
ones with a one-day season once they have two days.

At 15 minutes a one-day season is 96 steps, and those structures take minutes each to fit; the ones
without a season take seconds. --quick fits only the first two candidates, which have no season.

Every fit is checkpointed in artifacts/luzon/checkpoints, so an interrupted run resumes where it
stopped; --fresh ignores the checkpoints and fits everything again. Settings come from config.json.

ARIMA has no epochs: each fit is one optimization, and the log shows how many iterations it took
(at most model.maxiter). --show-iterations prints the log-likelihood after every iteration.

    python 04_pretrain_luzon.py                     days, folds and candidates from config.json
    python 04_pretrain_luzon.py --quick             first 2 candidates only: seconds
    python 04_pretrain_luzon.py --fresh             refit everything
    python 04_pretrain_luzon.py --show-iterations   watch each fit improve
"""

import argparse
import json
import os
import sys

from wattcast import iemop, model, pipeline, settings, steps
from wattcast.config import CONFIG


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=CONFIG["luzon"]["days"], help="most recent days of Luzon data to use")
    ap.add_argument("--folds", type=int, default=CONFIG["luzon"]["folds"], help="held-out windows")
    ap.add_argument("--quick", action="store_true", help="try only the first 2 candidates")
    ap.add_argument("--fresh", action="store_true", help="ignore checkpoints and fit everything again")
    ap.add_argument("--show-iterations", action="store_true",
                    help="print the log-likelihood after every optimizer iteration of every fit")
    args = ap.parse_args()
    if args.show_iterations:
        CONFIG["model"]["show_iterations"] = True

    try:
        y = iemop.load_demand(settings.LUZON_DEMAND).iloc[-args.days * steps.PER_DAY:]
    except (FileNotFoundError, ValueError) as e:
        sys.exit(str(e))
    print(f"Luzon demand: {steps.hours(int(y.notna().sum()), y.index):g} hours in {steps.MINUTES}-minute steps, "
          f"{y.index[0]} to {y.index[-1]}; holding out the last {args.folds} windows of "
          f"{CONFIG['luzon']['horizon_hours']} hours")
    ckpt = pipeline.luzon_checkpoints(fresh=args.fresh)
    result = pipeline.pretrain(y, model.CANDIDATES[:2] if args.quick else model.CANDIDATES, args.folds, ckpt)
    for name, b in result["baselines"].items():
        print(f"  baseline {name:<15} MASE {b['mase']}  WAPE {b['wape']}  window total off by {b['window_total_error']}")
    os.makedirs(settings.LUZON_DIR, exist_ok=True)
    with open(settings.LUZON_MODEL, "w") as f:
        json.dump(result, f, indent=2)
    run = result["run"]
    print(f"{run['checkpoints']['fitted']} fitted, {run['checkpoints']['from_checkpoint']} from checkpoints, "
          f"{run['seconds']:.0f}s; checkpoints and config in {settings.LUZON_CHECKPOINTS}")
    if run["not_converged"]:
        print(f"  {len(run['not_converged'])} fit(s) stopped at the iteration cap without converging: "
              + "; ".join(run["not_converged"]))
        print("  Raise model.maxiter in config.json and run again (only those are refitted).")
    print(f"-> {settings.LUZON_MODEL}")


if __name__ == "__main__":
    main()
