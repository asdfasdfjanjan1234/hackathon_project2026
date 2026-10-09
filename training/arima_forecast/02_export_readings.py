"""Export the device readings as hourly AI energy, one file per device.

    python 02_export_readings.py                  every device in the database
    python 02_export_readings.py --device-id 3
    python 02_export_readings.py --gaps missing   see wattcast/readings.py for day / missing / zero

Reads the database set in backend/.env (DATABASE_URL, else backend/data/wattage.db) and writes
data/processed/device_<id>_hourly.csv and device_<id>_by_app.csv.
"""

import argparse
from contextlib import closing

from wattcast import pipeline, readings, settings
from wattcast.config import CONFIG
from app.services import storage


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device-id", type=int, help="only this device (see the list printed without it)")
    ap.add_argument("--gaps", choices=readings.GAPS, default=CONFIG["device"]["gaps"],
                    help="hours the reader didn't run: no AI use on days it ran (day), always unknown "
                         "(missing), or always no AI use (zero). Default: config.json")
    args = ap.parse_args()

    cfg = settings.backend_config()
    print(f"Database: {storage.describe(cfg.DATABASE)}")
    with closing(storage.connect(cfg.DATABASE)) as conn:
        devices = [d for d in storage.list_devices(conn) if args.device_id in (None, d["id"])]
        if not devices:
            print("No devices with readings. Start the device reader (dashboard or backend/collect.py).")
            return
        for d in devices:
            hourly, by_app = readings.hourly_ai_energy(conn, d["id"], args.gaps)
            label = f"device {d['id']} ({d['name'] or 'unnamed'}, {d['os'] or '?'})"
            if hourly.empty:
                print(f"{label}: no readings")
                continue
            hourly.to_csv(settings.device_data(d["id"], "hourly.csv"))
            by_app.to_csv(settings.device_data(d["id"], "by_app.csv"), index=False)
            known = int(hourly["wh"].notna().sum())
            days = len(set(hourly.index[hourly["wh"].notna()].date))
            agents = readings.agent_series(hourly, by_app)
            print(f"{label}: {known} known hours on {days} days, {hourly['ai_wh'].sum() / 1000:.4f} kWh of AI "
                  f"-> {settings.device_data(d['id'], 'hourly.csv')}")
            print("  agents: " + ", ".join(f"{a} ({agents[a].sum() / 1000:.4f} kWh)" for a in agents.columns))
            if known < pipeline.MIN_HOURS:
                print(f"  needs {pipeline.MIN_HOURS} known hours to fine-tune: keep the device reader running")


if __name__ == "__main__":
    main()
