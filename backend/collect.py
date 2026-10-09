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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between samples (default 2)")
    args = parser.parse_args()
    # Stop cleanly on `kill` too, not only Ctrl+C.
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    conn = storage.connect(Config.DB_PATH)
    collector = Collector(conn, args.interval)
    print(f"Collecting into {Config.DB_PATH}. Press Ctrl+C to stop.")
    fitted = collector.model.fitted_on
    print(f"Power model: {'fitted on %d readings' % fitted if fitted else 'defaults (fits after ~8 minutes of readings)'}\n")
    print(f"{'time':8}  {'CPU%':>5}  {'GPU%':>5}  {'est W':>6}  {'meas W':>6}  {'AI W':>5}  AI apps")

    ai_wh = 0.0
    try:
        while True:
            time.sleep(args.interval)
            s = collector.step()
            ai_w = sum(a["watts"] for a in s["apps"])
            ai_wh += ai_w * args.interval / 3600
            apps = ", ".join(f"{a['model'] or a['app']} {a['watts']:.2f}W" for a in s["apps"]) or "-"
            measured = f"{s['measured_watts']:6.1f}" if s["measured_watts"] is not None else "     -"
            print(f"{datetime.now():%H:%M:%S}  {s['cpu']:5.1f}  {s['gpu']:5.1f}  {s['est_watts']:6.1f}  "
                  f"{measured}  {ai_w:5.2f}  {apps}", flush=True)
    except KeyboardInterrupt:
        print(f"\nStopped. AI apps used about {ai_wh:.2f} Wh this session.")


if __name__ == "__main__":
    main()
