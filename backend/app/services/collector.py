"""Samples device resources while AI apps run and stores per-app energy. Started by collect.py."""

import time

import psutil

from . import storage
from .ai_processes import find_ai_processes, split_ollama_by_model
from .attribution import PowerModel, attribute, fit_power_model
from .measurement import read_battery_telemetry, read_gpu_utilization

REFIT_EVERY = 5  # refit the power model after this many new telemetry readings


class Collector:
    def __init__(self, conn, interval=2.0):
        self.conn = conn
        self.interval = interval
        self.ncpu = psutil.cpu_count() or 1
        self.model = storage.get_power_model(conn) or PowerModel()
        self._last_ts = None
        self._last_tel = None
        self._skip_first_window = True  # it started before we did, so our samples don't cover it
        self._window = []  # (cpu, gpu) since the last telemetry update
        self._new_windows = 0
        # Prime CPU counters: the first reading of each is always 0.
        psutil.cpu_percent(None)
        find_ai_processes()

    def step(self):
        ts = time.time()
        interval_s = ts - self._last_ts if self._last_ts else self.interval
        self._last_ts = ts

        cpu = psutil.cpu_percent(None)
        gpu = read_gpu_utilization() or 0.0
        apps = attribute(self.model, gpu, split_ollama_by_model(find_ai_processes()), self.ncpu)
        measured = self._update_telemetry(ts, cpu, gpu)
        est = self.model.total(cpu, gpu)

        storage.save_sample(self.conn, ts, interval_s, cpu, gpu, est, measured, apps)
        return {"ts": ts, "cpu": cpu, "gpu": gpu, "est_watts": est, "measured_watts": measured, "apps": apps}

    def _update_telemetry(self, ts, cpu, gpu):
        tel = read_battery_telemetry()
        if not tel:
            return None
        self._window.append((cpu, gpu))
        last, self._last_tel = self._last_tel, tel
        if last is None or tel["count"] == last["count"]:
            return tel["watts"]
        if tel["count"] < last["count"] or self._skip_first_window:
            # Counters reset, or this window started before the collector did.
            self._skip_first_window = False
        else:
            avg_watts = (tel["accum"] - last["accum"]) / (tel["count"] - last["count"]) / 1000
            n = len(self._window)
            storage.save_window(self.conn, ts, avg_watts,
                                sum(c for c, _ in self._window) / n, sum(g for _, g in self._window) / n, n)
            self._new_windows += 1
            if self._new_windows >= REFIT_EVERY:
                self._refit()
        self._window = []
        return tel["watts"]

    def _refit(self):
        self._new_windows = 0
        fitted = fit_power_model(storage.recent_windows(self.conn))
        if fitted:
            self.model = fitted
            storage.set_power_model(self.conn, fitted)
