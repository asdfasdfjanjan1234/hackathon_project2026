"""Hourly forecast of the extra electricity bill from a device's AI use, with seasonal ARIMA.

    iemop      Luzon grid demand by hour, from IEMOP's public market data (pre-training data)
    readings   a device's AI energy by hour, from the backend's readings database
    patterns   usage levels (idle / light / moderate / heavy) and when they happen
    features   calendar inputs: the weekly cycle and Philippine holidays
    model      seasonal ARIMA on log energy: fit, warm start, forecast, simulate
    backtest   held-out forecasts against simple baselines
    bill       hourly kWh forecast -> pesos on the household's tariff
"""

from . import settings  # noqa: F401  (puts the backend on the import path first)
