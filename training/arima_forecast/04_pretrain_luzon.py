"""Pre-train: find the seasonal ARIMA that forecasts Luzon's hourly demand best, and save it.

Each candidate (model.CANDIDATES) is fitted on the hours before the last --folds days, then scored
on forecasting each of those days 24 hours ahead (backtest.py). The best by held-out MASE is
refitted on all the data and saved, with the whole comparison, to
artifacts/luzon/luzon_pretrained.json. Devices start from it in 05_finetune_device.py.

Every fit is checkpointed in artifacts/luzon/checkpoints, so an interrupted run resumes where it
stopped; --fresh ignores the checkpoints and fits everything again. Settings come from config.json.

ARIMA has no epochs: each fit is one optimization, and the log shows how many iterations it took
(at most model.maxiter). --show-iterations prints the log-likelihood after every iteration.

    python 04_pretrain_luzon.py                     days, folds and candidates from config.json
    python 04_pretrain_luzon.py --days 30 --quick   first 2 candidates only, for a fast check
    python 04_pretrain_luzon.py --fresh             refit everything
    python 04_pretrain_luzon.py --show-iterations   watch each fit improve
"""

import argparse
import json
import os

import pandas as pd

from wattcast import model, pipeline, settings
from wattcast.config import CONFIG


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=CONFIG["luzon"]["days"], help="most recent days of Luzon data to use")
    ap.add_argument("--folds", type=int, default=CONFIG["luzon"]["folds"], help="held-out days")
    ap.add_argument("--quick", action="store_true", help="try only the first 2 candidates")
    ap.add_argument("--fresh", action="store_true", help="ignore checkpoints and fit everything again")
    ap.add_argument("--show-iterations", action="store_true",
                    help="print the log-likelihood after every optimizer iteration of every fit")
    args = ap.parse_args()
    if args.show_iterations:
        CONFIG["model"]["show_iterations"] = True

    mwh = pd.read_csv(settings.LUZON_HOURLY, parse_dates=["hour"], index_col="hour")["mwh"].asfreq("h")
    y = mwh.iloc[-args.days * 24:]
    print(f"Luzon demand: {y.notna().sum()} hours, {y.index[0]} to {y.index[-1]}; holding out the last {args.folds} days")
    ckpt = pipeline.luzon_checkpoints(fresh=args.fresh)
    result = pipeline.pretrain(y, model.CANDIDATES[:2] if args.quick else model.CANDIDATES, args.folds, ckpt)
    for name, b in result["baselines"].items():
        print(f"  baseline {name:<15} MASE {b['mase']}  WAPE {b['wape']}  day total off by {b['day_total_error']}")
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
