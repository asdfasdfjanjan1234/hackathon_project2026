"""Turns device resource readings into watts.

The Mac's battery controller reports the average system power about once a
minute. We fit

    watts ≈ idle + w_cpu · CPU% + w_gpu · GPU%

to those readings with non-negative least squares, which calibrates the
formula to this specific machine. The formula then gives watts every few
seconds, and each AI app gets the share matching its CPU use (and GPU use
for local model runners), kept as separate CPU, GPU and memory watts so each
can be monitored. Idle power is never assigned to an app.

Where the OS measures CPU or GPU power directly (RAPL, nvidia-smi, IOReport),
apps get their share of that measured power above idle instead of the formula.
Until the formula is fitted, defaults for the kind of device are used.
"""

from dataclasses import asdict, dataclass
from itertools import combinations

import numpy as np

MIN_WINDOWS = 8          # telemetry readings needed before fitting
MIN_SPREAD_PCT = 3.0     # a resource must vary this much (std dev) to fit its coefficient
ACTIVE_CPU_PCT = 1.0     # % of one core: a model runner below this isn't generating


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


def default_power_model(system=None):
    """Starting coefficients for this kind of device, until enough readings are fitted.

    Order-of-magnitude figures: an Apple M2 laptop (~20 W at full load), a Windows/Linux
    laptop (~30 W CPU), a desktop (~65 W CPU, ~150 W for a discrete GPU at full load).
    Everything computed from them is labeled estimated.
    """
    system = system or {}
    if system.get("apple_silicon") or not system:
        return PowerModel()
    discrete = any(g.get("type") == "discrete" for g in system.get("gpus") or [])
    if (system.get("device") or {}).get("type") == "laptop":
        return PowerModel(idle_watts=6.0, watts_per_cpu_pct=0.30, watts_per_gpu_pct=0.30 if discrete else 0.10)
    return PowerModel(idle_watts=40.0, watts_per_cpu_pct=0.65, watts_per_gpu_pct=1.5 if discrete else 0.15)


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


def _gpu_shares(apps, gpu_by_pid, gpu_pids):
    """Each app's share of the GPU's power above idle (list aligned with apps)."""
    pids = [set(a.get("pids") or []) for a in apps]
    total = sum(gpu_by_pid.values()) if gpu_by_pid else 0
    if total > 0:
        # 1. The OS reports GPU use per process (Windows): any AI app gets its own share.
        return [sum(gpu_by_pid.get(p, 0.0) for p in ps) / total for ps in pids]
    if gpu_pids:
        # 2. NVIDIA lists the processes doing GPU compute: only local runners in that list.
        users = [a["kind"] == "local" and bool(ps & gpu_pids) for a, ps in zip(apps, pids)]
    else:
        # 3. Otherwise assume active local model runners are what's using the GPU.
        users = [a["kind"] == "local" and a["cpu_percent"] >= ACTIVE_CPU_PCT for a in apps]
    cpu = [a["cpu_percent"] if u else 0.0 for a, u in zip(apps, users)]
    if sum(cpu) > 0:
        return [c / sum(cpu) for c in cpu]
    n = sum(users)
    return [1 / n if u else 0.0 for u in users] if n else [0.0] * len(apps)


def attribute(model, gpu_pct, apps, ncpu, cpu_pct=None, measured=None, gpu_by_pid=None, gpu_pids=None,
              memory_est=0.0):
    """Set each app's watts and its parts: cpu_watts, gpu_watts, memory_watts, plus gpu_share.
    App CPU % is per core (can exceed 100), so divide by core count.

    `measured` = {"cpu": W, "gpu": W, "memory": W} above idle, for components with a power sensor.
    CPU: with a sensor, the app's share of all CPU use × measured CPU power; else the formula.
    GPU: measured GPU power (else the formula), split by who used the GPU (_gpu_shares).
    Memory: traffic follows compute, so the memory power above idle (measured, else `memory_est`)
    is split by each app's share of the CPU and GPU watts. Holding RAM adds no power (refresh
    runs either way), so a loaded model that isn't generating gets none. When CPU watts come
    from the formula, its coefficient already covers the memory traffic CPU work causes, so
    that part moves from cpu_watts to memory_watts instead of being counted twice.
    """
    measured = measured or {}
    cpu_measured = "cpu" in measured and bool(cpu_pct)
    gpu_total = measured["gpu"] if "gpu" in measured else model.watts_per_gpu_pct * gpu_pct
    memory_total = measured.get("memory", memory_est)
    shares = _gpu_shares(apps, gpu_by_pid, gpu_pids)
    parts = []
    for a, share in zip(apps, shares):
        app_pct = a["cpu_percent"] / ncpu  # % of the whole CPU
        if cpu_measured:
            cpu_w = measured["cpu"] * min(app_pct / cpu_pct, 1.0)
        else:
            cpu_w = model.watts_per_cpu_pct * app_pct
        parts.append((cpu_w, gpu_total * share))
    if cpu_measured:
        cpu_total = measured["cpu"]
    elif cpu_pct is not None:
        cpu_total = model.watts_per_cpu_pct * cpu_pct
    else:
        cpu_total = sum(c for c, _ in parts)
    compute_total = cpu_total + gpu_total
    for a, share, (cpu_w, gpu_w) in zip(apps, shares, parts):
        memory_w = memory_total * min((cpu_w + gpu_w) / compute_total, 1.0) if compute_total > 0 else 0.0
        if not cpu_measured:
            moved = min(memory_w, cpu_w)
            cpu_w -= moved
            if "memory" not in measured:
                memory_w = moved
        a.update(cpu_watts=round(cpu_w, 3), gpu_watts=round(gpu_w, 3), memory_watts=round(memory_w, 3),
                 gpu_share=round(share, 3), watts=round(cpu_w + gpu_w + memory_w, 3))
    return apps
