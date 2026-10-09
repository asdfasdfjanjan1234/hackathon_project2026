"""Seasonal ARIMA on the log of hourly energy, built on the series' weekly routine (features.py).

    z = (log1p(y) - mean) / std      y: one AI agent's hourly Wh on a device, or Luzon's hourly MWh
    z = routine + c * holiday + SARIMA(p,d,q)(P,D,Q,24) errors

`routine` is when the series is usually high or low across the week (when the user uses the agent,
and how heavily). ARIMA is fitted to the departures from it, z - routine: how a day runs above or
below the usual, and how that carries into the next hours. The routine enters as it is, with no
fitted multiplier, so it means the same thing in training and in a forecast made after it has been
re-learned from more readings.
The log makes a heavy hour and a light hour differ by a ratio, as usage levels do, and keeps
forecasts at or above zero. Standardizing puts the Luzon grid and one laptop on the same scale, so
the coefficients fitted on the grid are a starting point for a device: fine-tuning re-estimates
them on the device's own hours, starting from the grid's values (warm start).

Missing hours (NaN) are handled by the Kalman filter: they're neither zeros nor dropped.
Point forecasts are medians (expm1 of the forecast log); ranges cover INTERVAL of outcomes.

There are no epochs. A fit is one optimization: statsmodels adjusts the coefficients by maximum
likelihood (L-BFGS) until the log-likelihood stops improving, and every iteration uses the whole
series. The iterations are the nearest thing to epochs: at most MAXITER, and each fit records how
many it took and whether it converged before that cap.
"""

import warnings
from dataclasses import asdict, dataclass, field, replace

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from .config import CONFIG
from .features import calendar, routine_profile

DAY = 24
INTERVAL = CONFIG["model"]["interval"]  # forecast ranges: 0.8 is the 10th to the 90th percentile
MAXITER = CONFIG["model"]["maxiter"]


@dataclass(frozen=True)
class Spec:
    order: tuple
    seasonal_order: tuple

    @property
    def label(self):
        (p, d, q), (P, D, Q, s) = self.order, self.seasonal_order
        if not any((p, d, q, P, D, Q)):
            return "Routine only"
        return f"SARIMA({p},{d},{q})({P},{D},{Q},{s})"


# Tried on the Luzon grid by 04_pretrain_luzon.py; the best ones carry over to devices.
CANDIDATES = [Spec(tuple(order), tuple(seasonal)) for order, seasonal in CONFIG["luzon"]["candidates"]]
# The routine (and holiday) with no ARIMA terms: what the ARIMA part has to improve on.
ROUTINE_ONLY = Spec((0, 0, 0), (0, 0, 0, 0))


@dataclass
class Model:
    spec: Spec
    params: dict        # SARIMAX parameter name -> value, on the standardized log scale
    mean: float         # of log1p(y) in the training data
    std: float
    routine: list       # 7 x 24 typical z by day of week and hour (features.routine_profile)
    exog: list          # fitted inputs besides the routine: ["holiday"] or none
    trained: dict = field(default_factory=dict)  # data range, AIC, warm start

    def to_dict(self):
        d = asdict(self)
        d["spec"] = {"order": list(self.spec.order), "seasonal_order": list(self.spec.seasonal_order),
                     "label": self.spec.label}
        return d

    @classmethod
    def from_dict(cls, d):
        spec = Spec(tuple(d["spec"]["order"]), tuple(d["spec"]["seasonal_order"]))
        return cls(spec, d["params"], d["mean"], d["std"], d["routine"], d["exog"], d.get("trained", {}))

    def to_z(self, y):
        return (np.log1p(y.clip(lower=0)) - self.mean) / self.std

    def from_z(self, z):
        return np.maximum(np.expm1(z * self.std + self.mean), 0)  # works on arrays and pandas alike

    def _routine(self, index):
        return calendar(index, self.routine)["routine"]

    def _inputs(self, index):
        return calendar(index, self.routine)[self.exog] if self.exog else None

    def _sarimax(self, y):
        return SARIMAX(self.to_z(y) - self._routine(y.index), exog=self._inputs(y.index),
                       order=self.spec.order, seasonal_order=self.spec.seasonal_order, trend="n")

    def filter(self, y):
        """Run the model over `y` with its fitted parameters, ready to forecast from the end of `y`."""
        mod = self._sarimax(y)
        return mod.filter(np.array([self.params[n] for n in mod.param_names]))

    def _future(self, y, steps):
        index = pd.date_range(y.index[-1] + pd.Timedelta(hours=1), periods=steps, freq="h")
        return index, self._inputs(index)

    def forecast(self, y, steps):
        """Hourly median, low and high for the `steps` hours after `y` ends, in y's units."""
        index, exog = self._future(y, steps)
        f = self.filter(y).get_forecast(steps, exog=exog).summary_frame(alpha=1 - INTERVAL)
        departure = pd.DataFrame({"median": f["mean"].to_numpy(), "low": f["mean_ci_lower"].to_numpy(),
                                  "high": f["mean_ci_upper"].to_numpy()}, index=index)
        return self.from_z(departure.add(self._routine(index), axis=0))

    def simulate(self, y, steps, paths=500, seed=0):
        """`paths` possible futures of the `steps` hours after `y`, as an array (steps, paths) in y's units.
        Totals over many hours (a day, the billing cycle) take their range from these, since adding up
        each hour's range would overstate it."""
        index, exog = self._future(y, steps)
        sims = self.filter(y).simulate(steps, anchor="end", repetitions=paths, exog=exog, random_state=seed)
        departures = np.asarray(sims, dtype=float).reshape(steps, paths)
        return self.from_z(departures + self._routine(index).to_numpy()[:, None])

    def backtest_forecasts(self, y, origins, horizon):
        """{origin position: forecast of y[origin : origin + horizon]} from only the hours before
        each origin. The coefficients stay as fitted (before the first origin); the routine is
        re-learned from the hours before each origin, as it is whenever the model is refreshed
        with new readings, and as the baselines are (they see every hour before the origin too)."""
        out = {}
        for pos in origins:
            past = y.iloc[:pos]
            refreshed = replace(self, routine=routine_profile(self.to_z(past)))
            out[pos] = refreshed.forecast(past, horizon)["median"]
        return out


def fit(y, spec, start=None, maxiter=MAXITER, source="", on_iteration=None):
    """Fit `spec` to the hourly series `y` (regular hourly index, NaN = not measured).

    start: parameters of the same structure fitted elsewhere (the Luzon model) to start the optimizer
    from; names it doesn't have start from statsmodels' defaults. The holiday input is left out when
    no observed hour falls on a holiday, since nothing could be learned about it.
    on_iteration: called as on_iteration(number, log_likelihood) after each optimizer iteration, to
    watch a fit improve. Computing the log-likelihood for it costs one more pass per iteration.
    """
    observed = y.notna()
    logged = np.log1p(y.clip(lower=0))
    mean, std = float(logged.mean()), float(logged.std())
    std = std if std > 0 else 1.0
    routine = routine_profile((logged - mean) / std)
    exog = ["holiday"] if calendar(y.index, routine).loc[observed, "holiday"].nunique() > 1 else []
    model = Model(spec, {}, mean, std, routine, exog)
    mod = model._sarimax(y)
    start_params = None
    if start:
        missing = [n for n in mod.param_names if n not in start]
        default = dict(zip(mod.param_names, mod.start_params)) if missing else {}
        start_params = np.array([start.get(n, default.get(n)) for n in mod.param_names], dtype=float)
    iterations = [0]

    def after_iteration(params):  # params are in the optimizer's unconstrained space
        iterations[0] += 1
        if on_iteration:
            on_iteration(iterations[0], float(mod.loglike(params, transformed=False)))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # statsmodels warns when a fit doesn't converge: recorded below instead
        res = mod.fit(start_params=start_params, disp=False, maxiter=maxiter, callback=after_iteration)
    optimizer = getattr(res, "mle_retvals", None) or {}
    model.params = {n: float(v) for n, v in zip(mod.param_names, res.params)}
    model.trained = {"source": source, "start": str(y.index[0]), "end": str(y.index[-1]),
                     "hours": int(len(y)), "observed_hours": int(observed.sum()),
                     "aic": round(float(res.aic), 2), "loglike": round(float(res.llf), 3),
                     "iterations": int(optimizer.get("iterations", iterations[0])), "max_iterations": int(maxiter),
                     "converged": bool(optimizer.get("converged", True)), "warm_start": bool(start)}
    return model
