"""Samples device resources while AI apps run and stores per-app energy. Started by collect.py."""

import time

import psutil

from . import storage
from .ai_processes import find_ai_processes, label_active_models
from .attribution import attribute, default_power_model, fit_power_model
from .local_models import label_local_models
from .measurement import Sensors, estimate_memory_watts
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
        self.device_id = storage.register_device(conn, self.sensors.system)
        self.default_model = default_power_model(self.sensors.system)
        self.model = storage.get_power_model(conn, self.device_id) or self.default_model
        self.idle = {}  # lowest measured watts per component this session: never assigned to apps
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
        gpu_by_pid = self.sensors.gpu_by_pid()
        gpu_pids = None if gpu_by_pid else self.sensors.gpu_compute_pids()
        if ts - self._models_checked >= MODELS_EVERY_S:
            self._models_checked = ts
            self.active_models = latest_models()
        apps = label_active_models(label_local_models(find_ai_processes()), self.active_models)
        measured = self._update_telemetry(ts, cpu, gpu, self.sensors.system_power())
        components = self.sensors.components(cpu, gpu, self.model, measured)
        memory_est = estimate_memory_watts(self.sensors.system.get("memory_gb", 8), max(cpu, gpu), active_only=True)
        apps = attribute(self.model, gpu, apps, self.ncpu, cpu_pct=cpu, measured=self._above_idle(components),
                         gpu_by_pid=gpu_by_pid, gpu_pids=gpu_pids, memory_est=memory_est)
        est = self._estimate_total(cpu, gpu, components)

        storage.save_sample(self.conn, ts, interval_s, cpu, gpu, est, measured, apps, components,
                            self.device_id)
        return {"ts": ts, "cpu": cpu, "gpu": gpu, "est_watts": est, "measured_watts": measured,
                "components": components, "apps": apps}

    def _above_idle(self, components):
        """Measured CPU, GPU and memory watts above the lowest seen this session (their idle power)."""
        out = {}
        for part in ("cpu", "gpu", "memory"):
            c = components.get(part)
            if c and c["source"] != "estimated":
                self.idle[part] = min(self.idle.get(part, c["watts"]), c["watts"])
                out[part] = c["watts"] - self.idle[part]
        return out

    def _estimate_total(self, cpu, gpu, components):
        """Whole-machine watts from the formula, with measured CPU/GPU power in place of their terms."""
        est = self.model.total(cpu, gpu)
        for part, term in (("cpu", self.model.watts_per_cpu_pct * cpu), ("gpu", self.model.watts_per_gpu_pct * gpu)):
            c = components.get(part)
            if c and c["source"] != "estimated":
                est += c["watts"] - term
        return max(est, 0.0)

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
        fitted = fit_power_model(storage.recent_windows(self.conn, device_id=self.device_id), self.default_model)
        if fitted:
            self.model = fitted
            storage.set_power_model(self.conn, fitted, self.device_id)
