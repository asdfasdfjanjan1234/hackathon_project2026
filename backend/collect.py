"""Collects device power and AI app resource usage into the database.

    python collect.py                 # sample every 2 seconds until Ctrl+C
    python collect.py --interval 5

Leave it running while you use AI tools. The dashboard reads the results
when USE_SAMPLE_DATA=false in .env.
"""

import argparse
import signal
import time
from datetime import datetime

from app.config import Config
from app.services import storage
from app.services.collector import Collector


def print_devices(s):
    def names(items, fmt):
        return ", ".join(fmt(i) for i in items) or "none found"

    def disk(d):
        return "{} ({}, {} GB)".format(d["name"], d["type"], d["size_gb"])

    device, battery = s["device"], s["battery"]
    print(f"Detected {s['os']} {s['os_version']} ({s['arch']}) on a {device['type']}: {device['model'] or 'unknown model'}")
    print(f"  CPU       {s['cpu']}, {s['cpu_cores']['physical']} cores, {s['memory_gb']} GB RAM")
    print(f"  GPU       {names(s['gpus'], lambda g: g['name'] + ' (' + g['type'] + ')')}")
    print(f"  NPU       {names(s['npus'], lambda n: n['name'])}")
    print(f"  Disks     {names(s['disks'], disk)}")
    print(f"  Displays  {names(s['displays'], lambda d: d['name'] + (' (built-in)' if d.get('built_in') else ''))}")
    if battery:
        print(f"  Battery   {battery['percent']}%, {'plugged in' if battery['plugged_in'] else 'on battery'}")
    else:
        print("  Battery   none (desktop)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between samples (default 2)")
    args = parser.parse_args()
    # Stop cleanly on `kill` too, not only Ctrl+C.
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    conn = storage.connect(Config.DB_PATH)
    collector = Collector(conn, args.interval)
    print_devices(collector.sensors.system)
    print("Power readings:")
    for part, sensor in collector.sensors.sources().items():
        print(f"  {part:9} {sensor or 'estimated'}")
    print(f"Collecting into {Config.DB_PATH}. Press Ctrl+C to stop.")
    fitted = collector.model.fitted_on
    print(f"Power model: {'fitted on %d readings' % fitted if fitted else 'defaults (fits after ~8 minutes of readings)'}\n")
    print(f"{'time':8}  {'CPU%':>5}  {'GPU%':>5}  {'est W':>6}  {'meas W':>6}  "
          f"{'cpu W':>6}  {'gpu W':>6}  {'mem W':>6}  {'disk W':>6}  {'AI W':>5}  AI apps")

    ai_wh = 0.0
    try:
        while True:
            time.sleep(args.interval)
            s = collector.step()
            ai_w = sum(a["watts"] for a in s["apps"])
            ai_wh += ai_w * args.interval / 3600
            apps = ", ".join(f"{a['model'] or a['app']} {a['watts']:.2f}W" for a in s["apps"]) or "-"
            measured = f"{s['measured_watts']:6.1f}" if s["measured_watts"] is not None else "     -"
            # "~" marks an estimate, no mark a measured value.
            parts = "  ".join(f"{c['watts']:5.2f}{'~' if c['source'] == 'estimated' else ' '}"
                              for name, c in s["components"].items() if name != "other")
            print(f"{datetime.now():%H:%M:%S}  {s['cpu']:5.1f}  {s['gpu']:5.1f}  {s['est_watts']:6.1f}  "
                  f"{measured}  {parts}  {ai_w:5.2f}  {apps}", flush=True)
    except KeyboardInterrupt:
        print(f"\nStopped. AI apps used about {ai_wh:.2f} Wh this session.")


if __name__ == "__main__":
    main()
