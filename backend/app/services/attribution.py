"""Turns device resource readings into watts.

The Mac's battery controller reports the average system power about once a
minute. We fit

    watts ≈ idle + w_cpu · CPU% + w_gpu · GPU%

to those readings with non-negative least squares, which calibrates the
formula to this specific machine. The formula then gives watts every few
seconds, and each AI app gets the share matching its CPU use (and GPU use
for local model runners). Idle power is never assigned to an app.
"""

from dataclasses import asdict, dataclass
from itertools import combinations

import numpy as np

MIN_WINDOWS = 8          # telemetry readings needed before fitting
MIN_SPREAD_PCT = 3.0     # a resource must vary this much (std dev) to fit its coefficient


def nnls(A, b):
    """Non-negative least squares, exact for a few columns: try every subset of
    coefficients that may be non-zero and keep the best fit with none negative."""
    n = A.shape[1]
    best, best_err = np.zeros(n), float(np.sum(b ** 2))
    for k in range(1, n + 1):
        for cols in combinations(range(n), k):
            coef, *_ = np.linalg.lstsq(A[:, cols], b, rcond=None)
            if np.all(coef >= 0):
                x = np.zeros(n)
                x[list(cols)] = coef
                err = float(np.sum((A @ x - b) ** 2))
                if err < best_err:
                    best, best_err = x, err
    return best, best_err


@dataclass
class PowerModel:
    # Defaults are rough Apple M2 figures, used until enough readings are collected.
    idle_watts: float = 3.0
    watts_per_cpu_pct: float = 0.15
    watts_per_gpu_pct: float = 0.10
    fitted_on: int = 0  # number of telemetry readings; 0 means defaults

    def total(self, cpu_pct, gpu_pct):
        return self.idle_watts + self.watts_per_cpu_pct * cpu_pct + self.watts_per_gpu_pct * gpu_pct

    def to_dict(self):
        return asdict(self)


def fit_power_model(windows, default=None):
    """Fit from [(avg_watts, avg_cpu_pct, avg_gpu_pct)]. Returns None if the data can't support a fit."""
    default = default or PowerModel()
    if len(windows) < MIN_WINDOWS:
        return None
    data = np.asarray(windows, dtype=float)
    watts, cpu, gpu = data[:, 0], data[:, 1], data[:, 2]
    if cpu.std() < MIN_SPREAD_PCT:
        return None

    if gpu.std() >= MIN_SPREAD_PCT:
        A = np.column_stack([np.ones(len(data)), cpu, gpu])
        (idle, w_cpu, w_gpu), _ = nnls(A, watts)
    else:
        # GPU barely changed, so its coefficient can't be learned: keep the default.
        w_gpu = default.watts_per_gpu_pct
        A = np.column_stack([np.ones(len(data)), cpu])
        (idle, w_cpu), _ = nnls(A, watts - w_gpu * gpu)
    return PowerModel(float(idle), float(w_cpu), float(w_gpu), fitted_on=len(data))


def attribute(model, gpu_pct, apps, ncpu):
    """Set apps[i]["watts"]. App CPU % is per core (can exceed 100), so divide by core count.

    GPU power goes only to local model runners, which dominate GPU use while running.
    """
    local_cpu = sum(a["cpu_percent"] for a in apps if a["kind"] == "local")
    gpu_watts = model.watts_per_gpu_pct * gpu_pct
    for a in apps:
        cpu_w = model.watts_per_cpu_pct * a["cpu_percent"] / ncpu
        gpu_w = gpu_watts * a["cpu_percent"] / local_cpu if a["kind"] == "local" and local_cpu > 0 else 0.0
        a["watts"] = round(cpu_w + gpu_w, 3)
    return apps
