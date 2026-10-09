"""Download Luzon grid data from IEMOP and build the demand series used for pre-training,
in steps of step_minutes (config.json).

    python 01_download_iemop.py             download new daily files, then rebuild luzon_demand.csv
    python 01_download_iemop.py --offline   rebuild from the files already in data/raw/iemop

IEMOP's public page keeps about 90 days. Files already downloaded are kept, so running this every
few weeks builds a longer history.
"""

import argparse
import os

from wattcast import iemop, settings, steps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="don't download; use the files already saved")
    ap.add_argument("--pages", type=int, default=10, help="download pages to try, 24 days each (default 10)")
    args = ap.parse_args()

    if not args.offline:
        new = iemop.download(settings.RAW_IEMOP, args.pages)
        print(f"Downloaded {len(new)} new daily files into {settings.RAW_IEMOP}")
    demand = iemop.demand(settings.RAW_IEMOP, iemop.REGIONS["luzon"])
    os.makedirs(settings.PROCESSED, exist_ok=True)
    demand.to_csv(settings.LUZON_DEMAND, index_label="time")
    print(f"Luzon: {demand.notna().sum()} steps of {steps.MINUTES} minutes from {demand.index[0]} to "
          f"{demand.index[-1]} ({demand.isna().sum()} missing) -> {settings.LUZON_DEMAND}")


if __name__ == "__main__":
    main()
