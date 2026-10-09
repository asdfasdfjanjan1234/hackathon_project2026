"""Luzon grid demand by hour, from IEMOP's public RTD Regional Summaries (iemop.ph -> Market Data).

Each daily file RTDREG_YYYYMMDD.csv has one row per 5-minute dispatch interval, region and commodity:

    TIME_INTERVAL   end of the interval, e.g. "9/15/2026 12:05:00 AM" (Philippine time)
    REGION_NAME     CLUZ Luzon, CVIS Visayas, CMIN Mindanao
    COMMODITY_TYPE  En energy; Dr, Fr, Rd, Ru are reserves
    MKT_REQT        MW the market had to supply in the region in that interval

The public page keeps about the last 90 days, 24 files per download page, newest first. Run the
download again every few weeks to build a longer history: files already saved are kept.
"""

import io
import os
import re
import shutil
import urllib.request
import zipfile

import pandas as pd

DOWNLOAD_URL = ("https://www.iemop.ph/market-data/rtd-regional-summaries/"
                "?post=5760&sort=desc&page={page}&start=&end=")
FILE_RE = re.compile(r"^RTDREG_\d{8}\.csv$")
REGIONS = {"luzon": "CLUZ", "visayas": "CVIS", "mindanao": "CMIN"}
MIN_INTERVALS = 10  # of an hour's 12 five-minute intervals, for the hour to count


def download(dest, max_pages=10, timeout=120):
    """Save the daily files from IEMOP's public download pages into `dest`. Returns the new file names."""
    os.makedirs(dest, exist_ok=True)
    new = []
    for page in range(1, max_pages + 1):
        req = urllib.request.Request(DOWNLOAD_URL.format(page=page), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        if not body.startswith(b"PK"):  # past the last page the site returns an HTML page, not a zip
            break
        new += save_files(body, dest)
    return sorted(new)


def save_files(zip_bytes, dest):
    """Save the daily files in a downloaded zip that aren't in `dest` yet. Returns their names."""
    new = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for name in z.namelist():
            base = os.path.basename(name)
            # Only daily files, by exact name, so nothing in the archive is written anywhere else.
            if not FILE_RE.match(base) or os.path.exists(os.path.join(dest, base)):
                continue
            with z.open(name) as src, open(os.path.join(dest, base), "wb") as out:
                shutil.copyfileobj(src, out)
            new.append(base)
    return new


def read_day(path, region="CLUZ"):
    """One region's demand (MW) for each 5-minute interval in a daily file, indexed by interval end."""
    df = pd.read_csv(path, usecols=["TIME_INTERVAL", "REGION_NAME", "COMMODITY_TYPE", "MKT_REQT"], dtype=str)
    df = df[(df["REGION_NAME"] == region) & (df["COMMODITY_TYPE"] == "En")]
    text = df["TIME_INTERVAL"].str.strip()
    text = text.where(text.str.contains(":"), text + " 12:00:00 AM")  # midnight is written as a bare date
    end = pd.to_datetime(text, format="%m/%d/%Y %I:%M:%S %p")
    return pd.Series(pd.to_numeric(df["MKT_REQT"], errors="coerce").to_numpy(), index=end).dropna()


def hourly_demand(folder, region="CLUZ"):
    """A region's average demand in each clock hour (MW, so also MWh in that hour), from every daily
    file in `folder`. The interval ending 1:00 AM belongs to the 12 AM hour; 1:05 AM to the 1 AM hour.
    Hours with fewer than MIN_INTERVALS intervals are missing (NaN)."""
    files = sorted(f for f in os.listdir(folder) if FILE_RE.match(f)) if os.path.isdir(folder) else []
    if not files:
        raise FileNotFoundError(f"No RTDREG_*.csv files in {folder}: run 01_download_iemop.py first")
    mw = pd.concat(read_day(os.path.join(folder, f), region) for f in files).sort_index()
    mw = mw[~mw.index.duplicated()]
    by_hour = mw.groupby((mw.index - pd.Timedelta(seconds=1)).floor("h"))
    hourly = by_hour.mean().where(by_hour.count() >= MIN_INTERVALS)
    hours = pd.date_range(hourly.index.min(), hourly.index.max(), freq="h")
    return hourly.reindex(hours).rename("mwh")
