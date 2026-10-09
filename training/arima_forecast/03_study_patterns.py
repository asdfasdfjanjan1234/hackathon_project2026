"""Study when and how heavily a device uses AI, per usage level and per AI agent, and Luzon's daily pattern.

    python 03_study_patterns.py --device-id 3   -> artifacts/devices/device_3_patterns.md / .json
    python 03_study_patterns.py --luzon         -> artifacts/luzon/luzon_patterns.md / .json
"""

import argparse
import json
import os

import pandas as pd

from wattcast import patterns, readings, settings


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

    if args.luzon:
        mwh = pd.read_csv(settings.LUZON_HOURLY, parse_dates=["hour"], index_col="hour")["mwh"].asfreq("h")
        report = patterns.study_grid(mwh)
        write(os.path.join(settings.LUZON_DIR, "luzon_patterns"), report, patterns.grid_markdown(report))
        return

    hourly = readings.load_hourly(settings.device_data(args.device_id, "hourly.csv"))
    by_app = readings.load_by_app(settings.device_data(args.device_id, "by_app.csv"))
    report = patterns.study_device(hourly, by_app, readings.agent_series(hourly, by_app))
    write(settings.device_artifact(args.device_id, "patterns"), report,
          patterns.device_markdown(args.device_id, report))


if __name__ == "__main__":
    main()
