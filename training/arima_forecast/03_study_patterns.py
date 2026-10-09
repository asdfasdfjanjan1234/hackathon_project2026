"""Study when and how heavily a device uses AI, per usage level and per AI agent, and Luzon's daily pattern.

    python 03_study_patterns.py --device-id 3   -> artifacts/devices/device_3_patterns.md / .json
    python 03_study_patterns.py --luzon         -> artifacts/luzon/luzon_patterns.md / .json
"""

import argparse
import json
import os
import sys

from wattcast import iemop, patterns, readings, settings


def write(path_base, report, markdown):
    os.makedirs(os.path.dirname(path_base), exist_ok=True)
    with open(path_base + ".json", "w") as f:
        json.dump(report, f, indent=2)
    with open(path_base + ".md", "w") as f:
        f.write(markdown)
    print(markdown)
    print(f"-> {path_base}.md / .json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--device-id", type=int)
    group.add_argument("--luzon", action="store_true")
    args = ap.parse_args()

    try:
        if args.luzon:
            demand = iemop.load_demand(settings.LUZON_DEMAND)
        else:
            energy = readings.load_energy(settings.device_data(args.device_id, "energy.csv"))
            by_app = readings.load_by_app(settings.device_data(args.device_id, "by_app.csv"))
    except (FileNotFoundError, ValueError) as e:
        sys.exit(str(e))
    if args.luzon:
        report = patterns.study_grid(demand)
        write(os.path.join(settings.LUZON_DIR, "luzon_patterns"), report, patterns.grid_markdown(report))
        return

    report = patterns.study_device(energy, by_app, readings.agent_series(energy, by_app))
    write(settings.device_artifact(args.device_id, "patterns"), report,
          patterns.device_markdown(args.device_id, report))


if __name__ == "__main__":
    main()
