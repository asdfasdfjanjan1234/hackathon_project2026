"""Score a device's fine-tuning checkpoints as an "in use / idle" classifier: accuracy, precision,
recall and F1.

The models forecast Wh per step, so these scores need a yes/no question first: is the agent in use
in this step? A step is "in use" when its energy, as Wh per hour, is at least agents.used_wh in
config.json (0.05 Wh per hour = 0.0125 Wh per 15-minute step). The forecast and the actual reading of
every held-out step are each turned into in use / idle and compared (wattcast/classify.py):

    accuracy    share of held-out steps called right
    precision   of the steps forecast "in use", the share that were ("–" when none were)
    recall      of the steps that were in use, the share forecast "in use"
    f1          the harmonic mean of precision and recall

"Always idle" is listed as a yardstick: on a mostly idle device it scores a high accuracy by never
saying "in use", so compare accuracy with it, and look at F1. The model fine-tuning picked is marked ★.
The dashboard shows the same scores (Billing Projection → Forecast accuracy).

Nothing is fitted. The held-out forecasts are read from the backtest checkpoints in
artifacts/devices/device_<id>_checkpoints, and the actual readings from data/processed. If the
readings were exported again after fine-tuning, run 05_finetune_device.py first so they match.

    python 08_classification_metrics.py --device-id 1
    python 08_classification_metrics.py --device-id 1 --used-wh 0.02
    python 08_classification_metrics.py --device-id 1 --sweep
"""

import argparse
import sys

from wattcast import classify


def _pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def _name(r):
    return ("★ " if r["chosen"] else "") + r["model"]


def table(rows):
    lines = ["| Model | Accuracy | Precision | Recall | F1 | TP | FP | FN | TN |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {_name(r)} | {_pct(r['accuracy'])} | {_pct(r['precision'])} | {_pct(r['recall'])} | "
                     f"{_pct(r['f1'])} | {r['tp']} | {r['fp']} | {r['fn']} | {r['tn']} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-id", type=int, required=True)
    ap.add_argument("--used-wh", type=float, default=classify.USED_WH,
                    help="Wh per hour from which a step counts as in use (default agents.used_wh)")
    ap.add_argument("--sweep", action="store_true",
                    help=f"also score at {', '.join(map(str, classify.SWEEP_WH))} Wh per hour")
    args = ap.parse_args()

    try:
        rep = classify.report(args.device_id, classify.SWEEP_WH if args.sweep else (), args.used_wh)
    except (FileNotFoundError, ValueError) as e:
        sys.exit(str(e))
    at = {t["used_wh"]: t for t in rep["thresholds"]}
    main_t = at[args.used_wh]
    for agent, rows in main_t["agents"].items():
        r = rows[0]
        in_use = sum(x["tp"] + x["fn"] for x in rows if x["chosen"])
        print(f"\nDevice {args.device_id}, {agent}: {r['steps']} held-out steps, {in_use} in use "
              f"(at least {args.used_wh:g} Wh per hour = {main_t['per_step_wh']:.4g} Wh per step)\n")
        print(table(rows))

    if args.sweep:
        for agent in main_t["agents"]:
            print(f"\nF1 / accuracy by threshold, {agent}:\n")
            print("| Model | " + " | ".join(f"{wh:g} Wh/h" for wh in at) + " |")
            print("|---|" + "---:|" * len(at))
            for i, r in enumerate(main_t["agents"][agent]):
                cells = [f"{_pct(t['agents'][agent][i]['f1'])} / {_pct(t['agents'][agent][i]['accuracy'])}"
                         for t in at.values()]
                print(f"| {_name(r)} | " + " | ".join(cells) + " |")
            print("\nIn-use held-out steps per threshold: "
                  + ", ".join(f"{wh:g}: {t['in_use_steps']}" for wh, t in at.items()))


if __name__ == "__main__":
    main()
