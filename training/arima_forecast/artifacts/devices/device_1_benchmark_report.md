# WattTrace Model Benchmark & Accuracy Report (Device 1)

Generated: 2026-10-10T03:10:57 | Overall Status: **PASS**

## 1. Quality & Consistency Checks

| Test | Status | Detail |
| --- | --- | --- |
| Regular 15-minute time steps | PASS | Consistent intervals |
| Non-negative energy inputs | PASS | Physical reality |
| Non-negative forecast bounds (kWh & cost >= 0) | PASS | Energy & cost cannot be negative |
| Ordered confidence intervals (low <= median <= high) | PASS | Valid distribution |
| Bill projection additivity (Baseline + AI) | PASS | ₱1500.13 == ₱1500.13 |
| 80% Interval Empirical Coverage (81.2%) | PASS | Calibrated prediction bounds |
| Sub-150ms inference latency | PASS | 3.2ms per day |

## 2. Accuracy Benchmark Comparison

| Model | MAE (Wh) | RMSE (Wh) | WAPE | MASE | Window Total Err | Rel. to Naive |
| --- | --- | --- | --- | --- | --- | --- |
| ★ WattTrace ARIMA (Ours) | 0.00750 | 0.01490 | 125.68% | 9.3172 | 142.21% | BASELINE |
| Seasonal Naive | 0.00770 | 0.01510 | 129.73% | 9.6178 | 160.40% | +2.6% vs ARIMA |
| Profile | 0.00770 | 0.01510 | 129.73% | 9.6178 | 160.40% | +2.6% vs ARIMA |
| Last Value | 0.00600 | 0.01480 | 100.00% | 7.4136 | 100.00% | -25.0% vs ARIMA |
| Historical Mean | 0.00710 | 0.01470 | 118.68% | 8.7985 | 116.68% | -5.6% vs ARIMA |

## 3. Latency & Performance Benchmarks

- **24-hour forecast latency:** `3.19 ms`
- **7-day forecast latency:** `5.40 ms`
- **500-path Monte Carlo simulation:** `14.12 ms`
- **Empirical coverage:** `81.2%` (target: 80%)
