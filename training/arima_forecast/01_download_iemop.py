"""Download Luzon grid data from IEMOP and build the hourly series used for pre-training.

    python 01_download_iemop.py             download new daily files, then rebuild luzon_hourly.csv
    python 01_download_iemop.py --offline   rebuild from the files already in data/raw/iemop

IEMOP's public page keeps about 90 days. Files already downloaded are kept, so running this every
few weeks builds a longer history.
"""

import argparse
import os

from wattcast import iemop, settings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="don't download; use the files already saved")
    ap.add_argument("--pages", type=int, default=10, help="download pages to try, 24 days each (default 10)")
    args = ap.parse_args()

    if not args.offline:
        new = iemop.download(settings.RAW_IEMOP, args.pages)
        print(f"Downloaded {len(new)} new daily files into {settings.RAW_IEMOP}")
    hourly = iemop.hourly_demand(settings.RAW_IEMOP, iemop.REGIONS["luzon"])
    os.makedirs(settings.PROCESSED, exist_ok=True)
    hourly.to_csv(settings.LUZON_HOURLY, index_label="hour")
    print(f"Luzon: {hourly.notna().sum()} hours from {hourly.index[0]} to {hourly.index[-1]} "
          f"({hourly.isna().sum()} missing) -> {settings.LUZON_HOURLY}")


if __name__ == "__main__":
    main()
