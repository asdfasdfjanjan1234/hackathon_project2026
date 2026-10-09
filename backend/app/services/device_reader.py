"""Runs the collector in a background thread, so reading starts from the dashboard's
"Start reading my device" button instead of a separate `python collect.py`.

The backend runs on the user's own computer: a browser can't read hardware or local
logs, so this process does it and the dashboard shows the results.
"""

import threading
import time
import traceback
from contextlib import closing

from . import storage
from .collector import Collector
from .measurement import default_sensors


class DeviceReader:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.started_at = None
        self.samples = 0
        self.last = None
        self.error = None
        self.power_model = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, db_path, interval=2.0):
        """Start reading. Returns False if this reader or collect.py is already running."""
        with self._lock:
            if self.running:
                return False
            with closing(storage.connect(db_path)) as conn:
                if storage.latest_sample(conn):  # collect.py is already writing samples
                    return False
            self._stop.clear()
            self.started_at, self.samples, self.last, self.error = time.time(), 0, None, None
            self._thread = threading.Thread(target=self._run, args=(db_path, interval),
                                            name="device-reader", daemon=True)
            self._thread.start()
            return True

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread:
            thread.join(timeout=10)

    def _run(self, db_path, interval):
        try:
            # SQLite connections belong to the thread that opened them.
            with closing(storage.connect(db_path)) as conn:
                collector = Collector(conn, interval, sensors=default_sensors())
                self.power_model = collector.model.to_dict()
                while not self._stop.wait(interval):
                    try:
                        self.last = collector.step()
                        self.samples += 1
                        self.power_model = collector.model.to_dict()
                        self.error = None
                    except Exception as e:  # one bad reading shouldn't end the session
                        self.error = f"{type(e).__name__}: {e}"
                        traceback.print_exc()
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            traceback.print_exc()

    def status(self, db_path):
        with closing(storage.connect(db_path)) as conn:
            external = not self.running and storage.latest_sample(conn) is not None
            stored = storage.sample_count(conn)
        last = self.last or {}
        return {
            "running": self.running,
            "external_collector": external,  # collect.py is running in a terminal instead
            "started_at": self.started_at,
            "samples": self.samples,
            "stored_samples": stored,
            "error": self.error,
            "power_model": self.power_model,
            "latest": {
                "ts": last.get("ts"),
                "cpu_percent": last.get("cpu"),
                "gpu_percent": last.get("gpu"),
                "est_watts": last.get("est_watts"),
                "measured_watts": last.get("measured_watts"),
                "components": last.get("components"),
                "apps": last.get("apps", []),
            } if last else None,
        }


reader = DeviceReader()
