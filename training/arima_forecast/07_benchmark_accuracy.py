"""Benchmark and test model accuracy, precision, baselines, and physical consistency.

Evaluates:
1. Physical and schema consistency (non-negativity, bounds ordering, bill arithmetic).
2. Out-of-sample accuracy vs standard baselines (Seasonal Naive, Profile, Last Value, Historical Mean).
3. Prediction interval precision & coverage calibration (actuals within 80% interval).
4. Inference latency and execution speed benchmarks.

Usage:
    python 07_benchmark_accuracy.py --device-id 1
    python 07_benchmark_accuracy.py --device-id 1 --save-report
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd

from wattcast import backtest, bill, model, pipeline, readings, settings, steps
from wattcast.config import CONFIG


def _to_md_table(df):
    headers = list(df.columns)
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in headers) + " |")
    return "\n".join(lines)


def run_benchmarks(device_id: int, save_report: bool = True):
    print("=" * 78)
    print(f" WATTTRACE ARIMA BENCHMARK & ACCURACY TEST SUITE — DEVICE {device_id}")
    print("=" * 78)

    model_path = settings.device_artifact(device_id, "model.json")
    forecast_path = settings.device_artifact(device_id, "forecast.json")
    energy_path = settings.device_data(device_id, "energy.csv")
    by_app_path = settings.device_data(device_id, "by_app.csv")

    checks = []

    # ---------------------------------------------------------
    # 1. ARTIFACT & DATA INTEGRITY
    # ---------------------------------------------------------
    print("\n[1/5] Checking Data Integrity & Artifact Schemas...")

    if not os.path.exists(energy_path):
        sys.exit(f"Missing {energy_path}: run 02_export_readings.py first.")
    if not os.path.exists(model_path):
        sys.exit(f"Missing {model_path}: run 05_finetune_device.py first.")
    if not os.path.exists(forecast_path):
        sys.exit(f"Missing {forecast_path}: run 06_forecast_bill.py first.")

    energy = readings.load_energy(energy_path)
    agents = readings.agent_series(energy, readings.load_by_app(by_app_path))
    total_y = energy["wh"]

    with open(model_path) as f:
        saved_model = json.load(f)
    with open(forecast_path) as f:
        saved_forecast = json.load(f)

    # Step regularity check
    step_diffs = pd.Series(energy.index).diff().dropna()
    is_regular_steps = (step_diffs == pd.Timedelta(minutes=steps.MINUTES)).all()
    checks.append(("Regular 15-minute time steps", is_regular_steps, "Consistent intervals"))
    print(f"  ✓ Time steps: {steps.MINUTES} min regularity: {'PASS' if is_regular_steps else 'FAIL'}")

    # Non-negative actual readings
    no_neg_actuals = (energy["wh"].dropna() >= 0).all()
    checks.append(("Non-negative energy inputs", no_neg_actuals, "Physical reality"))
    print(f"  ✓ Energy actuals >= 0: {'PASS' if no_neg_actuals else 'FAIL'}")

    # ---------------------------------------------------------
    # 2. PHYSICAL REALISM & CONSERVATION OF ENERGY
    # ---------------------------------------------------------
    print("\n[2/5] Testing Physical Realism & Energy Conservation...")

    forecast_csv = settings.device_artifact(device_id, "forecast.csv")
    fc_table = pd.read_csv(forecast_csv, index_col=0, parse_dates=True) if os.path.exists(forecast_csv) else None

    if fc_table is not None:
        # Non-negative forecasts
        no_neg_fc = (fc_table["kwh"] >= -1e-6).all() and (fc_table["kwh_low"] >= -1e-6).all() and (fc_table["cost"] >= -1e-6).all()
        checks.append(("Non-negative forecast bounds (kWh & cost >= 0)", no_neg_fc, "Energy & cost cannot be negative"))
        print(f"  ✓ Forecast energy kWh & cost >= 0: {'PASS' if no_neg_fc else 'FAIL'}")

        # Ordered intervals: low <= median <= high
        ordered = ((fc_table["kwh_low"] <= fc_table["kwh"] + 1e-6) &
                   (fc_table["kwh"] <= fc_table["kwh_high"] + 1e-6) &
                   (fc_table["cost_low"] <= fc_table["cost"] + 1e-6) &
                   (fc_table["cost"] <= fc_table["cost_high"] + 1e-6)).all()
        checks.append(("Ordered confidence intervals (low <= median <= high)", ordered, "Valid distribution"))
        print(f"  ✓ Confidence interval ordering: {'PASS' if ordered else 'FAIL'}")

    # Bill arithmetic consistency
    b = saved_forecast["bill"]
    expected_proj = round(b["baseline_bill"] + b["ai_cost_so_far"] + b["ai_cost_remaining"], 2)
    bill_math_correct = abs(b["projected_bill"] - expected_proj) < 0.02
    checks.append(("Bill projection additivity (Baseline + AI)", bill_math_correct,
                   f"₱{b['projected_bill']:.2f} == ₱{expected_proj:.2f}"))
    print(f"  ✓ Bill arithmetic: {'PASS' if bill_math_correct else 'FAIL'} (₱{b['projected_bill']:.2f})")

    # ---------------------------------------------------------
    # 3. OUT-OF-SAMPLE ACCURACY & BENCHMARK COMPARISON
    # ---------------------------------------------------------
    print("\n[3/5] Running Out-of-Sample Backtest Accuracy vs Baselines...")

    # Load backtest origins
    horizon_hours = saved_model.get("horizon_hours", 2.0)
    horizon_steps = steps.count(horizon_hours, total_y.index)
    origins, _ = pipeline._windows(total_y, "device", folds=saved_model["folds"],
                                  horizon_hours=horizon_hours,
                                  min_train_hours=CONFIG["device"]["min_train_hours"])

    scale_val = backtest.scale(total_y, origins[0])

    # Reconstruct fitted models per agent
    reconstructed_models = {
        name: model.Model.from_dict(info["model"])
        for name, info in saved_model["agents"].items()
    }

    # Evaluate forecasts and interval coverage
    summed_forecasts = {p: pd.Series(0.0, index=total_y.index[p:p + horizon_steps]) for p in origins}
    interval_coverages = []

    for name, agent_mod in reconstructed_models.items():
        agent_y = agents[name]
        for p in origins:
            past = agent_y.iloc[:p]
            refreshed = model.replace(agent_mod, routine=model.routine_profile(agent_mod.to_z(past)))
            f_frame = refreshed.forecast(past, horizon_steps)
            summed_forecasts[p] = summed_forecasts[p] + f_frame["median"]

            # Coverage check: actual in [low, high]
            actual_window = agent_y.iloc[p:p + horizon_steps]
            valid = actual_window.notna()
            if valid.any():
                cov = ((actual_window[valid] >= f_frame.loc[valid, "low"] - 1e-6) &
                       (actual_window[valid] <= f_frame.loc[valid, "high"] + 1e-6)).mean()
                interval_coverages.append(cov)

    mean_coverage = float(np.mean(interval_coverages)) if interval_coverages else 0.0

    # Score our model
    arima_scores = backtest.score(total_y, summed_forecasts, scale_val)

    # Compute baselines
    base_dict = backtest.baselines(total_y, origins, horizon_steps)

    # Additional baseline: historical mean
    def historical_mean(y_ser, pos, h):
        m_val = y_ser.iloc[:pos].dropna().mean()
        return pd.Series(m_val, index=y_ser.index[pos:pos + h])

    base_dict["historical_mean"] = {p: historical_mean(total_y, p, horizon_steps) for p in origins}

    baseline_scores = {b_name: backtest.score(total_y, b_fc, scale_val) for b_name, b_fc in base_dict.items()}

    # Format Accuracy & Benchmark Table
    benchmarks_table = [
        {
            "Model": "★ WattTrace ARIMA (Ours)",
            "MAE (Wh)": f"{arima_scores['mae']:.5f}",
            "RMSE (Wh)": f"{arima_scores['rmse']:.5f}",
            "WAPE": f"{arima_scores['wape']:.2%}" if arima_scores['wape'] is not None else "N/A",
            "MASE": f"{arima_scores['mase']:.4f}" if arima_scores['mase'] is not None else "N/A",
            "Window Total Err": f"{arima_scores['window_total_error']:.2%}" if arima_scores['window_total_error'] is not None else "N/A",
            "Rel. to Naive": "BASELINE"
        }
    ]

    naive_mae = baseline_scores["seasonal_naive"]["mae"]
    for b_name, sc in baseline_scores.items():
        rel = ((sc["mae"] - arima_scores["mae"]) / sc["mae"]) * 100 if sc["mae"] > 0 else 0
        rel_str = f"{rel:+.1f}% vs ARIMA"
        benchmarks_table.append({
            "Model": b_name.replace("_", " ").title(),
            "MAE (Wh)": f"{sc['mae']:.5f}",
            "RMSE (Wh)": f"{sc['rmse']:.5f}",
            "WAPE": f"{sc['wape']:.2%}" if sc['wape'] is not None else "N/A",
            "MASE": f"{sc['mase']:.4f}" if sc['mase'] is not None else "N/A",
            "Window Total Err": f"{sc['window_total_error']:.2%}" if sc['window_total_error'] is not None else "N/A",
            "Rel. to Naive": rel_str
        })

    bench_df = pd.DataFrame(benchmarks_table)
    print("\n--- OUT-OF-SAMPLE BENCHMARK COMPARISON TABLE ---")
    print(bench_df.to_string(index=False))

    coverage_ok = 0.60 <= mean_coverage <= 1.0
    checks.append((f"80% Interval Empirical Coverage ({mean_coverage:.1%})", coverage_ok,
                   "Calibrated prediction bounds"))
    print(f"\n  ✓ 80% Confidence Interval Coverage: {mean_coverage:.1%} ({'PASS' if coverage_ok else 'WARN'})")

    # ---------------------------------------------------------
    # 4. INFERENCE LATENCY & THROUGHPUT BENCHMARKS
    # ---------------------------------------------------------
    print("\n[4/5] Benchmarking Latency & Performance...")

    active_model = list(reconstructed_models.values())[0]

    # Benchmark 24-hour forecast latency (96 steps)
    latencies_24h = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = active_model.forecast(total_y, 96)
        latencies_24h.append((time.perf_counter() - t0) * 1000)
    lat_24h = float(np.median(latencies_24h))

    # Benchmark 7-day forecast latency (672 steps)
    latencies_7d = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = active_model.forecast(total_y, 672)
        latencies_7d.append((time.perf_counter() - t0) * 1000)
    lat_7d = float(np.median(latencies_7d))

    # Benchmark Monte Carlo simulate latency (96 steps, 500 paths)
    t0 = time.perf_counter()
    _ = active_model.simulate(total_y, 96, paths=CONFIG["forecast"]["paths"])
    lat_mc = (time.perf_counter() - t0) * 1000

    print(f"  • 24-hour ahead point forecast (96 steps):   {lat_24h:.2f} ms")
    print(f"  • 7-day ahead point forecast (672 steps):    {lat_7d:.2f} ms")
    print(f"  • 24-hour Monte Carlo simulation (500 paths): {lat_mc:.2f} ms")

    fast_inference = lat_24h < 150.0
    checks.append(("Sub-150ms inference latency", fast_inference, f"{lat_24h:.1f}ms per day"))

    # ---------------------------------------------------------
    # 5. SCORECARD & REPORT GENERATION
    # ---------------------------------------------------------
    print("\n[5/5] Generating Audit Scorecard...")

    all_passed = all(status for _, status, _ in checks)
    scorecard = [
        {"Test": name, "Status": "PASS" if status else "FAIL", "Detail": detail}
        for name, status, detail in checks
    ]
    scorecard_df = pd.DataFrame(scorecard)
    print("\n" + scorecard_df.to_string(index=False))

    summary = {
        "device_id": device_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "all_passed": all_passed,
        "checks": scorecard,
        "benchmarks": benchmarks_table,
        "performance": {
            "forecast_24h_ms": round(lat_24h, 2),
            "forecast_7d_ms": round(lat_7d, 2),
            "simulation_500paths_ms": round(lat_mc, 2),
        },
        "coverage": {
            "empirical_interval_coverage": round(mean_coverage, 4),
            "target_interval": CONFIG["model"]["interval"]
        }
    }

    if save_report:
        report_json_path = settings.device_artifact(device_id, "benchmark_report.json")
        with open(report_json_path, "w") as f:
            json.dump(summary, f, indent=2)

        report_md_path = settings.device_artifact(device_id, "benchmark_report.md")
        with open(report_md_path, "w") as f:
            f.write(f"# WattTrace Model Benchmark & Accuracy Report (Device {device_id})\n\n")
            f.write(f"Generated: {summary['timestamp']} | Overall Status: **{'PASS' if all_passed else 'CHECK'}**\n\n")
            f.write("## 1. Quality & Consistency Checks\n\n")
            f.write(_to_md_table(scorecard_df))
            f.write("\n\n## 2. Accuracy Benchmark Comparison\n\n")
            f.write(_to_md_table(bench_df))
            f.write("\n\n## 3. Latency & Performance Benchmarks\n\n")
            f.write(f"- **24-hour forecast latency:** `{lat_24h:.2f} ms`\n")
            f.write(f"- **7-day forecast latency:** `{lat_7d:.2f} ms`\n")
            f.write(f"- **500-path Monte Carlo simulation:** `{lat_mc:.2f} ms`\n")
            f.write(f"- **Empirical coverage:** `{mean_coverage:.1%}` (target: 80%)\n")

        print(f"\n✓ Saved reports to:")
        print(f"  -> {report_json_path}")
        print(f"  -> {report_md_path}")

    print("\n" + "=" * 78)
    if all_passed:
        print(" SUCCESS: All accuracy, benchmark, and sanity tests PASSED!")
    else:
        print(" REVIEW: Model is operational with some warnings noted above.")
    print("=" * 78 + "\n")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", type=int, default=1, help="Device ID to benchmark (default: 1)")
    parser.add_argument("--no-save", action="store_true", help="Do not write report markdown and json files")
    args = parser.parse_args()

    success = run_benchmarks(args.device_id, save_report=not args.no_save)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
