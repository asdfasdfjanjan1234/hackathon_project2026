"""Forecast of the extra electricity bill from a device's AI use, with ARIMA in 15-minute steps.

    steps      the time step every series is in (step_minutes in config.json)
    iemop      Luzon grid demand by step, from IEMOP's public market data (pre-training data)
    readings   a device's AI energy by step, from the backend's readings database
    patterns   usage levels (idle / light / moderate / heavy) and when they happen
    features   calendar inputs: the weekly cycle and Philippine holidays
    model      ARIMA on log energy, seasonal when the series is long enough: fit, warm start,
               forecast, simulate
    backtest   held-out forecasts against simple baselines
    bill       kWh forecast -> pesos on the household's tariff
"""

from . import settings  # noqa: F401  (puts the backend on the import path first)
