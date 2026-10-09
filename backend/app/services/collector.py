"""Samples device resources while AI apps run and stores per-app energy. Started by collect.py."""

import time

import psutil

from . import storage
from .ai_processes import find_ai_processes, label_active_models, split_ollama_by_model
from .attribution import PowerModel, attribute, fit_power_model
from .measurement import Sensors
from .model_usage import latest_models

REFIT_EVERY = 5  # refit the power model after this many new telemetry readings
WINDOW_S = 60    # Windows battery gives instant readings, so average them over this long
MODELS_EVERY_S = 15  # how often to re-read which cloud model each app is using


class Collector:
    def __init__(self, conn, interval=2.0, sensors=None):
        self.conn = conn
        self.interval = interval
        self.ncpu = psutil.cpu_count() or 1
        self.sensors = sensors or Sensors()  # detects the OS and picks its sensors
        self.model = storage.get_power_model(conn) or PowerModel()
        self.device_id = storage.register_device(conn, self.sensors.system)
        self._last_ts = None
        self._last_tel = None
        self._skip_first_window = True  # it started before we did, so our samples don't cover it
        self._window = []  # (cpu, gpu, watts) since the last telemetry window
        self._window_start = time.time()
        self._new_windows = 0
        self.active_models = {}
        self._models_checked = 0.0
        # Prime CPU counters: the first reading of each is always 0.
        psutil.cpu_percent(None)
        find_ai_processes()

    def step(self):
        ts = time.time()
        interval_s = ts - self._last_ts if self._last_ts else self.interval
        self._last_ts = ts

        cpu = psutil.cpu_percent(None)
        gpu = self.sensors.gpu_percent() or 0.0
        if ts - self._models_checked >= MODELS_EVERY_S:
            self._models_checked = ts
            self.active_models = latest_models()
        apps = label_active_models(split_ollama_by_model(find_ai_processes()), self.active_models)
        apps = attribute(self.model, gpu, apps, self.ncpu)
        measured = self._update_telemetry(ts, cpu, gpu, self.sensors.system_power())
        est = self.model.total(cpu, gpu)
        components = self.sensors.components(cpu, gpu, self.model, measured)

        storage.save_sample(self.conn, ts, interval_s, cpu, gpu, est, measured, apps, components,
                            self.device_id)
        return {"ts": ts, "cpu": cpu, "gpu": gpu, "est_watts": est, "measured_watts": measured,
                "components": components, "apps": apps}

    def _update_telemetry(self, ts, cpu, gpu, tel):
        if not tel:
            return None
        self._window.append((cpu, gpu, tel["watts"]))
        done, avg_watts = self._window_done(ts, tel)
        if not done:
            return tel["watts"]
        if avg_watts is not None:
            n = len(self._window)
            storage.save_window(self.conn, ts, avg_watts,
                                sum(c for c, _, _ in self._window) / n, sum(g for _, g, _ in self._window) / n, n,
                                self.device_id)
            self._new_windows += 1
            if self._new_windows >= REFIT_EVERY:
                self._refit()
        self._window = []
        self._window_start = ts
        return tel["watts"]

    def _window_done(self, ts, tel):
        """(has the current window ended?, its average watts, or None to discard it)."""
        if "accum" not in tel:
            # Instant readings only (Windows): end a window every WINDOW_S seconds.
            if ts - self._window_start < WINDOW_S:
                return False, None
            return True, sum(w for _, _, w in self._window) / len(self._window)
        # Mac battery controller: running totals that update about once a minute.
        last, self._last_tel = self._last_tel, tel
        if last is None or tel["count"] == last["count"]:
            return False, None
        if tel["count"] < last["count"] or self._skip_first_window:
            # Counters reset, or this window started before the collector did.
            self._skip_first_window = False
            return True, None
        return True, (tel["accum"] - last["accum"]) / (tel["count"] - last["count"]) / 1000

    def _refit(self):
        self._new_windows = 0
        fitted = fit_power_model(storage.recent_windows(self.conn))
        if fitted:
            self.model = fitted
            storage.set_power_model(self.conn, fitted)
