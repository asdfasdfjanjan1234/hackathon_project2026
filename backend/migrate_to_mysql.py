"""Copies readings from the SQLite file into the MySQL database in DATABASE_URL.

    python migrate_to_mysql.py                      # backend/data/wattage.db → DATABASE_URL
    python migrate_to_mysql.py --sqlite other.db

Readings stored before devices were tracked are assigned to this computer.
Running it again skips readings that were already copied.
"""

import argparse
import os
from contextlib import closing

from app.config import BACKEND_DIR, Config
from app.services import storage
from app.services.system_info import detect_system

COLUMNS = {
    "samples": "ts, interval_s, cpu_percent, gpu_percent, est_watts, measured_watts, device_id",
    "ai_samples": "ts, interval_s, app, model, kind, cpu_percent, rss_mb, watts, host, "
                  "cpu_watts, gpu_watts, memory_watts, gpu_share, vram_mb, model_mb, device_id",
    "component_samples": "ts, interval_s, component, watts, source, device_id",
    "power_windows": "ts, avg_watts, avg_cpu, avg_gpu, n_samples, device_id",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite", default=os.path.join(BACKEND_DIR, "data", "wattage.db"))
    args = parser.parse_args()
    if not storage.is_mysql(Config.DATABASE):
        parser.error("set DATABASE_URL=mysql://user:password@localhost:3306/ai_wattage in backend/.env first")
    if not os.path.exists(args.sqlite):
        parser.error(f"{args.sqlite} not found")

    with closing(storage.connect(args.sqlite)) as src, closing(storage.connect(Config.DATABASE)) as dst:
        # SQLite device ids → MySQL device ids; untagged readings were taken on this computer.
        ids = {None: storage.register_device(dst, detect_system())}
        for d in src.execute("SELECT * FROM devices").fetchall():
            ids[d["id"]] = storage.register_device(dst, {
                "machine_id": d["machine_id"], "hostname": d["name"], "os": d["os"], "os_version": d["os_version"],
                "arch": d["arch"], "cpu": d["cpu"], "memory_gb": d["memory_gb"], "device": {"model": d["model"]}})

        for table, columns in COLUMNS.items():
            have = {(r["ts"], r["device_id"]) for r in dst.execute(f"SELECT DISTINCT ts, device_id FROM {table}")}
            rows = [(*r[:-1], ids[r[-1]]) for r in
                    (tuple(row[c] for c in columns.split(", ")) for row in src.execute(f"SELECT {columns} FROM {table}"))]
            new = [r for r in rows if (r[0], r[-1]) not in have]
            placeholders = ", ".join("?" * len(columns.split(", ")))
            dst.executemany(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", new)
            dst.commit()
            print(f"{table:18} {len(new):6} copied, {len(rows) - len(new)} already there")

        model = storage.get_power_model(src)
        if model and not storage.get_power_model(dst):
            storage.set_power_model(dst, model)
            print("power model       copied")
    print(f"Done. Readings are in {storage.describe(Config.DATABASE)}.")


if __name__ == "__main__":
    main()
