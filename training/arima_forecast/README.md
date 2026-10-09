# Electricity bill forecast from AI agent usage patterns (seasonal ARIMA)

Forecasts a user's electricity bill from two things it learns on their device:

- **How each AI agent is used:** Claude Code, GitHub Copilot, Ollama and so on, each with its own energy pattern.
- **When it is used:** each agent's weekly routine, hour by hour. On a Peak/Off-Peak tariff the hour also sets the price.

The result of fine-tuning is **one seasonal ARIMA per AI agent**. Their hourly forecasts add up to the AI part of the bill:

```text
projected bill = baseline bill + AI cost measured so far this cycle + AI cost forecast for the hours left
```

- **Pre-trained on Philippine grid data:** Luzon hourly demand from IEMOP's public market data.
- **Fine-tuned per device and agent:** on that device's own readings from the collector.
- **Priced on the household's tariff:** flat rate, or Meralco Peak/Off-Peak, read from `backend/.env`.

Start with **[ai_bill_forecast.ipynb](ai_bill_forecast.ipynb)**. It runs every step with explanations and charts. The numbered scripts run the same steps from a terminal.

## Setup

Use Python 3.10 to 3.13. The pinned package versions have installers for those.

**Windows** (PowerShell or Command Prompt):

```bat
cd training\arima_forecast
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest
```

**macOS / Linux:**

```bash
cd training/arima_forecast
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

- `requirements.txt` includes the backend's packages, because the training code reuses the backend's database, `.env` and tariff code. Keep the folder inside the repo, next to `backend/`.
- `pytest` runs 28 quick checks on small made-up data (about 10 seconds). It trains nothing on your data and saves nothing.
- Run the scripts with the venv's Python: `.venv\Scripts\python 04_pretrain_luzon.py` on Windows, `.venv/bin/python 04_pretrain_luzon.py` on macOS / Linux.

In VS Code, open the notebook and pick the kernel at `training/arima_forecast/.venv`. The notebook and scripts read the same `backend/.env` as the app: the database (MySQL or SQLite), `ELECTRICITY_RATE`, `TARIFF`, `BASELINE_BILL` and `BILLING_CYCLE_START_DAY`.

## Steps

| # | Notebook section / script | What it does | Output |
|---|---|---|---|
| 1 | `01_download_iemop.py` | Downloads IEMOP's daily RTD Regional Summaries and averages Luzon's 5-minute demand into hourly MWh | `data/processed/luzon_hourly.csv` |
| 2 | `04_pretrain_luzon.py` | Backtests 6 seasonal ARIMA structures on Luzon and ranks them, keeping each one's coefficients | `artifacts/luzon/luzon_pretrained.json` |
| 3 | `02_export_readings.py` | Turns the collector's 2-second readings into hourly AI Wh, in total and per agent | `data/processed/device_<id>_hourly.csv`, `_by_app.csv` |
| 4 | `03_study_patterns.py` | Usage levels (idle / light / moderate / heavy), and when and how heavily each agent is used | `artifacts/devices/device_<id>_patterns.md` |
| 5 | `05_finetune_device.py` | Fits one model per agent on its weekly routine, warm-started from Luzon, and checks the summed forecast on held-out days | `artifacts/devices/device_<id>_model.json` |
| 6 | `06_forecast_bill.py` | Projected bill for the cycle, hourly kWh and pesos per agent, with 80% ranges | `artifacts/devices/device_<id>_forecast.csv` / `.json` |

Every script has `--help`. Pre-training on 60 days of Luzon data takes a few minutes the first time. Everything else takes seconds.

## Configuration

Every training setting is in **[config.json](config.json)**. The notebook and all the scripts read it, so a setting is changed in one place.

| Group | Settings |
|---|---|
| `luzon` | `days` of Luzon data to pre-train on, held-out `folds`, and the `candidates` structures to try |
| `device` | `gaps` (how hours without readings are treated), held-out `folds`, `top_structures` tried per agent, `allow_routine_only`, and the `min_hours` and `min_days` needed to fine-tune |
| `agents` | When an agent gets its own model: `min_used_hours`, `min_share`, `max_agents` |
| `model` | `maxiter` (the most optimizer iterations a fit may take), `show_iterations`, the forecast range `interval`, and `routine_prior_weight` |
| `forecast` | Simulated `paths` for the ranges, and the longest forecast in hours |
| `checkpoints` | `true` to save and reuse checkpoints |

[wattcast/config.py](wattcast/config.py) lists every setting with its meaning and default. A setting left out of `config.json` keeps its default. A name that isn't a real setting is an error, so a typo can't silently do nothing. Script flags such as `--days` and `--folds` override the file for one run.

The bill settings are not here. They stay in `backend/.env`, where the app reads them: `ELECTRICITY_RATE`, `TARIFF`, `POP_PEAK_RATE`, `POP_OFFPEAK_RATE`, `BASELINE_BILL` and `BILLING_CYCLE_START_DAY`.

## Iterations, not epochs

ARIMA training has no epochs. A neural network passes over the data many times, and each pass is an epoch. An ARIMA is fitted in **one optimization**: statsmodels adjusts a handful of coefficients by maximum likelihood (L-BFGS) until the log-likelihood stops improving. Every iteration of that optimizer uses the whole series, so its iterations are the nearest thing to epochs.

| If you're looking for | Here it is |
|---|---|
| Number of epochs | `model.maxiter` in `config.json`: the most iterations a fit may take (200). A fit stops earlier when it converges. |
| Loss per epoch | The log-likelihood after each iteration (higher is better). Off by default. Turn on with `--show-iterations`, `SHOW_ITERATIONS = True` in the notebook, or `model.show_iterations` in `config.json`. |
| Checkpoint per epoch | A checkpoint per fitted model (next section) |
| Validation set | The held-out days: `luzon.folds` and `device.folds` |

Every training log line ends with the iterations that fit took. The format (`...` stands for the scores):

```text
  SARIMA(1,0,1)(1,0,1,24)  MASE ...  WAPE ...  day total off by ...  [45 iterations]
```

With `--show-iterations`, each fit also prints one line per iteration. These lines are from a fit on the small made-up series the tests use:

```text
      fitting SARIMA(1,0,1)(1,0,1,24) on all hours
        ...
        iteration  42  log-likelihood 320.169
        iteration  43  log-likelihood 320.170
        iteration  44  log-likelihood 320.170
        iteration  45  log-likelihood 320.170
Best on Luzon: SARIMA(1,0,1)(1,0,1,24), fitted on all hours  [45 iterations]
```

Each checkpoint and model file saves `iterations`, `max_iterations`, `converged` and `loglike` for its fit. A fit that hits the cap is marked `NOT converged` in the log and listed under `not_converged` in the run record. To fix one, raise `model.maxiter` and run again; only the fits affected by the change are redone.

## Checkpoints

Training fits many models one after another: 6 structures on Luzon, and several candidates per AI agent on a device. Each one is saved **the moment it finishes**.

| Run | Checkpoint folder |
|---|---|
| Pre-training | `artifacts/luzon/checkpoints/` |
| Fine-tuning device 3 | `artifacts/devices/device_3_checkpoints/` |

- **One JSON file per fit.** It holds the fitted coefficients, the held-out forecasts and the scores.
- **Resume.** If a run is interrupted, running it again loads the finished fits and continues with the rest. The log marks them `(from checkpoint)`.
- **When a checkpoint is reused.** Only when the data, the model structure, the starting coefficients and the fit settings are exactly the same. New readings, or a changed setting, mean a new fit.
- **Start over.** `--fresh` (or `FRESH = True` in the notebook) ignores the checkpoints and replaces them.
- **Failed fits are recorded too,** so a resumed run doesn't spend time failing again.

**What each run saves about its configuration:**

- `config.json` inside the checkpoint folder: the settings, package versions and data range of the run that last wrote there.
- A `run` record inside the model file (`luzon_pretrained.json`, `device_<id>_model.json`): the same, plus start and finish times, how many fits came from checkpoints, and any fit that did not converge.
- For a device, the bill settings from `backend/.env` that the forecast used. Database credentials are never saved.

## How it works

**Model.** Each series (one agent's hourly Wh, or Luzon's hourly MWh) goes through `z = (log(1 + y) − mean) / std` and is fitted as

```text
z = routine + c · holiday + SARIMA(p,d,q)(P,D,Q) errors, with a 24-hour season
```

- `routine` is the series' own weekly pattern: its typical level in each of the 168 hours of the week, learned from the training hours. For an agent this is "when the user uses it, and how heavily". An hour with few readings is pulled toward the average for that hour on weekdays or weekends. How hard is estimated from the series, over all the hours of the week together: a habit that repeats every week is kept, and a one-off is smoothed away. So once some days have been seen twice, a day seen only once is trusted as much as the agent's regularity warrants.
- `holiday` marks Philippine public holidays (the `holidays` package).
- The seasonal ARIMA part is fitted to the departures from the routine: how a day runs above or below the usual, and how that carries into the next hours. The routine enters as it is, with no fitted multiplier.

The log turns usage levels into ratios and keeps forecasts at or above zero. Standardizing puts the grid (about 10,000 MWh an hour) and a laptop (a few Wh) on one scale.

**Agents.** An agent is the app that drew the power (`ai_samples.app`). Its models and the commands it runs ("tool runs") count as that agent. An agent gets its own model once it has 24 hours of use and 2% of the AI energy. Smaller ones are forecast together as "Other AI apps".

**Pre-train and fine-tune.** ARIMA has a handful of parameters and is always fitted to the series it forecasts. Luzon's long, regular history ranks the model *structures* and supplies *starting* coefficients for each. For every agent, fine-tuning fits three kinds of candidate and keeps the one with the lowest held-out error:

| Candidate | What it is |
|---|---|
| Routine only | The agent's weekly routine with no ARIMA terms. This is what ARIMA has to improve on. |
| Warm | A top Luzon structure, with the optimizer started from its Luzon coefficients |
| Cold | The same structure, started from statsmodels' defaults |

For an agent whose use is fully explained by its weekly routine, "Routine only" can win. Set `device.allow_routine_only` to `false` in `config.json` to always choose an ARIMA. The routine alone is then scored for comparison only.

**Checking it.** The backtest fits on the hours before the last 7 days, then forecasts each of those days 24 hours ahead, using only earlier hours. The coefficients stay as fitted, and the routine is re-learned from the hours before each held-out day. The agents' forecasts are added up and scored on the device's total AI energy against two baselines: the same hour yesterday, and the average for that hour of the week.

| Score | Meaning |
|---|---|
| MASE | Average error divided by the training error of "same hour yesterday". Below 1 is better than that rule. |
| WAPE | Total error as a share of total energy |
| day_total_error | How far off each day's total was. Closest to "how far off is the bill". |

If the summed forecast doesn't beat both baselines, the model file and the forecast say so (`beats_baselines: false`).

**Usage levels.** Idle is below 1 W of AI power. Active hours are split into thirds at the device's own 33rd and 67th percentiles (light / moderate / heavy), so "heavy" means heavy for that machine. Forecast hours are labeled with the same cut points.

**Bill.** Each forecast hour's kWh is multiplied by that hour's rate. On `TARIFF=pop`, peak and off-peak hours come from the backend's own `cheap_hours.py`. The projected bill adds `BASELINE_BILL`, the AI cost measured so far this cycle, and the forecast for the hours left.

Ranges are 80%, from 500 simulated futures per agent, so a total has its own range instead of a sum of hourly ones. Simulated futures only vary hour to hour around the learned routine and don't know the routine itself may be off. So a total's range is never narrower than the backtest's error on held-out day totals.

## Data

| Source | Where | Notes |
|---|---|---|
| IEMOP RTD Regional Summaries | iemop.ph → Market Data, public, no login | Daily `RTDREG_YYYYMMDD.csv`, 5-minute intervals. Luzon = `REGION_NAME CLUZ`, `COMMODITY_TYPE En`, demand = `MKT_REQT` (MW). The interval ending at midnight is written as a bare date. The public page keeps about 90 days, so re-run step 1 every few weeks to build a longer history. |
| Device readings | `backend/.env` database, tables `samples` and `ai_samples` | Needs at least **72 known hours on 3+ days** to fine-tune. Two weeks or more is better, because the weekly routine needs each hour of the week seen at least twice. |

**Hours the reader didn't run** (`device.gaps` in `config.json`, or `--gaps` on the export script):

| Value | Rule |
|---|---|
| `day` (default) | On a day the reader ran at least an hour, hours without readings count as no AI use (computer off or asleep), as in the backend's daily totals. A day with no readings is unknown. |
| `missing` | Only hours the reader ran at least half of count, scaled to the full hour. Everything else is unknown. |
| `zero` | Every hour without readings counts as no AI use. |

Unknown hours are missing values for the model, not zeros. The Kalman filter handles them.

## What's committed

- **Committed:** code, the notebook (without outputs), and `artifacts/luzon/` (from public data).
- **Ignored:** `data/` (downloads and exports), `artifacts/luzon/checkpoints/` (re-created by training), and `artifacts/devices/`, which describes one person's computer use.

## Using it in the app

The backend can load `device_<id>_model.json` and call `wattcast.pipeline.forecast(saved, agents, hourly, Config)` on the latest hourly readings. That returns the projected bill with its range, the hourly series, and the cost per agent, ready for `/api/forecast`. Refit weekly, or whenever a backtest score drifts.
