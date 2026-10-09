# Electricity bill forecast from AI agent usage patterns (ARIMA, 15-minute steps)

Forecasts a user's electricity bill from two things it learns on their device:

- **How each AI agent is used:** Claude Code, GitHub Copilot, Ollama and so on, each with its own energy pattern.
- **When it is used:** each agent's weekly routine, hour by hour. On a Peak/Off-Peak tariff the hour also sets the price.

The result of fine-tuning is **one ARIMA per AI agent**. Their forecasts add up to the AI part of the bill:

```text
projected bill = baseline bill + AI cost measured so far this cycle + AI cost forecast for the hours left
```

- **Pre-trained on Philippine grid data:** Luzon demand from IEMOP's public market data.
- **Fine-tuned per device and agent:** on that device's own readings from the collector.
- **Priced on the household's tariff:** flat rate, or Meralco Peak/Off-Peak, read from `backend/.env`.

Start with **[ai_bill_forecast.ipynb](ai_bill_forecast.ipynb)**. It runs every step with explanations and charts. The numbered scripts run the same steps from a terminal.

## 15-minute steps

Every series has one value per **step** of `step_minutes` in `config.json`: 15 minutes. A device that has been read for 8 hours has 32 steps to fit on, so it can be fine-tuned the same day. With hourly values it would need days.

| | 15-minute steps (the default) | Hourly, as it was (`step_minutes: 60` and the settings below) |
|---|---|---|
| Readings needed to fine-tune | 2 known hours | 72 known hours on 3+ days |
| Held-out check | The last windows of 30 minutes | The last days, a day ahead |
| Structures a device is fitted with | Without a season at first, with a one-day season after 2 days | With a one-day season |

**What a few hours can't tell.** The model learns when a device uses AI from the hours of the day it has been read in. An hour it hasn't seen yet is forecast at the device's average level. So a model fitted on one evening doesn't know the mornings, and its forecast for the rest of the billing cycle is rough until it has seen whole days. Fine-tuning and the forecast both print how many of the 24 hours the readings cover. Export and fine-tune again as readings come in.

**Changing the step.** Set `step_minutes` to 5, 10, 15, 20, 30 or 60, then run every step again from `01_download_iemop.py`. Files and models made at another step are refused with a message saying what to run. The durations in `config.json` are in hours and don't change with the step. For hourly modeling with a week or more of readings, also set `device.horizon_hours` to 24, `device.min_train_hours` to 48, `device.min_hours` to 72, `device.min_days` to 3 and `agents.min_used_hours` to 24.

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
- `pytest` runs 41 quick checks on small made-up data (about 10 seconds). It trains nothing on your data and saves nothing.
- Run the scripts with the venv's Python: `.venv\Scripts\python 04_pretrain_luzon.py` on Windows, `.venv/bin/python 04_pretrain_luzon.py` on macOS / Linux.

In VS Code, open the notebook and pick the kernel at `training/arima_forecast/.venv`. The notebook and scripts read the same `backend/.env` as the app: the database (MySQL or SQLite), `ELECTRICITY_RATE`, `TARIFF`, `BASELINE_BILL` and `BILLING_CYCLE_START_DAY`.

## Steps

| # | Notebook section / script | What it does | Output |
|---|---|---|---|
| 1 | `01_download_iemop.py` | Downloads IEMOP's daily RTD Regional Summaries and averages Luzon's 5-minute demand into 15-minute steps (MW) | `data/processed/luzon_demand.csv` |
| 2 | `04_pretrain_luzon.py` | Backtests 6 ARIMA structures on Luzon, 3 without a season and 3 with a one-day season, and ranks them, keeping each one's coefficients | `artifacts/luzon/luzon_pretrained.json` |
| 3 | `02_export_readings.py` | Turns the collector's 2-second readings into AI Wh per step, in total and per agent | `data/processed/device_<id>_energy.csv`, `_by_app.csv` |
| 4 | `03_study_patterns.py` | Usage levels (idle / light / moderate / heavy), and when and how heavily each agent is used | `artifacts/devices/device_<id>_patterns.md` |
| 5 | `05_finetune_device.py` | Fits one model per agent on its weekly routine, warm-started from Luzon, and checks the summed forecast on held-out windows | `artifacts/devices/device_<id>_model.json` |
| 6 | `06_forecast_bill.py` | Projected bill for the cycle, kWh and pesos per step and agent, with 80% ranges | `artifacts/devices/device_<id>_forecast.csv` / `.json` |
| 7 | `08_classification_metrics.py` | Scores the held-out forecasts as "AI in use / idle": accuracy, precision, recall and F1, next to the baselines. Fits nothing. The dashboard shows the same under **Forecast Accuracy** | printed |

Every script has `--help`.

**How long pre-training takes.** It uses 30 days of Luzon data (`luzon.days`). The three structures without a season fit in seconds. The three with a one-day season are slower, because at 15-minute steps a day is 96 steps: expect minutes each. That is an estimate from timing single passes over made-up data, not from a full run. `04_pretrain_luzon.py --quick` (or `QUICK = True` in the notebook) fits only the first two structures, which have no season, and takes seconds. Those are the structures a device is fitted with in its first two days, so `--quick` is enough to fine-tune a device today. Everything else takes seconds.

## Configuration

Every training setting is in **[config.json](config.json)**. The notebook and all the scripts read it, so a setting is changed in one place.

| Group | Settings |
|---|---|
| `step_minutes` | The length of a time step: 15. See [15-minute steps](#15-minute-steps). |
| `luzon` | `days` of Luzon data to pre-train on, the held-out windows (`folds` of them, `horizon_hours` long, after `min_train_hours` to fit on), and the `candidates` structures to try |
| `device` | `gaps` (how time without readings is treated), the held-out windows (`folds`, `horizon_hours`, `min_train_hours`), `top_structures` tried per agent, `allow_routine_only`, and the `min_hours` and `min_days` needed to fine-tune |
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
| Validation set | The held-out windows: `folds` and `horizon_hours` under `luzon` and `device` |

Every training log line ends with the iterations that fit took. The format (`...` stands for the scores):

```text
  SARIMA(1,0,1)(1,0,1,96)  MASE ...  WAPE ...  window total off by ...  [45 iterations]
```

With `--show-iterations`, each fit also prints one line per iteration. These lines are from a fit on the small made-up hourly series the tests use, where a day is 24 steps:

```text
      fitting SARIMA(1,0,1)(1,0,1,24) on all the data
        ...
        iteration  42  log-likelihood 320.169
        iteration  43  log-likelihood 320.170
        iteration  44  log-likelihood 320.170
        iteration  45  log-likelihood 320.170
Best on Luzon: SARIMA(1,0,1)(1,0,1,24), fitted on all the data  [45 iterations]
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

**Model.** Each series (one agent's Wh per step, or Luzon's MW) goes through `z = (log(1 + y) − mean) / std` and is fitted as

```text
z = routine + c · holiday + ARIMA(p,d,q) errors, with a seasonal part (P,D,Q) of one day when the series is long enough
```

- `routine` is the series' own weekly pattern: its typical level in each of the 168 hours of the week, learned from the training steps. Every step in an hour gets that hour's level, and an hour counts as one reading however short the steps are. For an agent this is "when the user uses it, and how heavily". An hour with few readings is pulled toward the average for that hour on weekdays or weekends. How hard is estimated from the series, over all the hours of the week together: a habit that repeats every week is kept, and a one-off is smoothed away. So once some days have been seen twice, a day seen only once is trusted as much as the agent's regularity warrants.
- `holiday` marks Philippine public holidays (the `holidays` package).
- The ARIMA part is fitted to the departures from the routine: how a day runs above or below the usual, and how that carries into the next steps. The routine enters as it is, with no fitted multiplier.

The log turns usage levels into ratios and keeps forecasts at or above zero. Standardizing puts the grid (about 10,000 MW) and a laptop (a few Wh a step) on one scale.

**Structures.** The candidates in `luzon.candidates` are of two kinds. A structure with a season is only tried on a series with two of its seasons to fit on.

| Kind | Label | Used on a device |
|---|---|---|
| No season | `ARIMA(p,d,q)` | From its first hours of readings |
| A one-day season, written `"day"` in `config.json`: 96 steps of 15 minutes | `SARIMA(p,d,q)(P,D,Q,96)` | Once it has two days to fit on |

**Agents.** An agent is the app that drew the power (`ai_samples.app`). Its models and the commands it runs ("tool runs") count as that agent. An agent gets its own model once it has 1 hour of use and 2% of the AI energy (`agents.min_used_hours`, `agents.min_share`). Smaller ones are forecast together as "Other AI apps".

**Pre-train and fine-tune.** ARIMA has a handful of parameters and is always fitted to the series it forecasts. Luzon's long, regular history ranks the model *structures* and supplies *starting* coefficients for each. For every agent, fine-tuning fits three kinds of candidate and keeps the one with the lowest held-out error:

| Candidate | What it is |
|---|---|
| Routine only | The agent's weekly routine with no ARIMA terms. This is what ARIMA has to improve on. |
| Warm | A top Luzon structure the device has enough readings for, with the optimizer started from its Luzon coefficients |
| Cold | The same structure, started from statsmodels' defaults |

For an agent whose use is fully explained by its weekly routine, "Routine only" can win. Set `device.allow_routine_only` to `false` in `config.json` to always choose an ARIMA. The routine alone is then scored for comparison only.

**Checking it.** The backtest holds out the last few windows of the series, fits on the steps before them, then forecasts each window from only the steps before it. The coefficients stay as fitted, and the routine is re-learned from the steps before each window.

| Series | Held-out windows | Fitted on at least |
|---|---|---|
| Luzon | The last 7 days, each forecast 24 hours ahead | 48 hours before them |
| A device | The last windows of 30 minutes, at most 6 | 1 hour before them |

The agents' forecasts are added up and scored on the device's total AI energy against three baselines.

| Baseline | Forecast |
|---|---|
| `seasonal_naive` | The same time the day before. Before a day of readings exists, the profile below. |
| `profile` | The average for that hour of the week so far |
| `last_value` | The last known step, held for the whole window |

| Score | Meaning |
|---|---|
| MASE | Average error divided by the training error of "same time yesterday" (before a day of readings exists: of "same as the step before"). Below 1 is better than that rule. |
| WAPE | Total error as a share of total energy |
| window_total_error | How far off each held-out window's total was. Closest to "how far off is the bill". |

If the summed forecast doesn't beat every baseline, the model file and the forecast say so (`beats_baselines: false`). A check on 30-minute windows says how well the next half hour is forecast. It says less about the rest of the billing cycle, which depends on the routine.

**Two hours of readings.** The defaults are set so a device can be fine-tuned after 2 hours: the last two 30-minute windows are held out, each forecast from the steps before it, after an hour to fit on. That makes fine-tuning run, and it takes under a second. It doesn't make the model reliable. One hour of held-out readings is too little to tell a good model from a lucky one, and the forecast for the rest of the billing cycle is close to "the average power of those 2 hours, for every hour left". With a day or more of readings, set `device.horizon_hours` to 2 and `device.min_train_hours` to 4 to check two hours ahead instead.

**Usage levels.** Idle is below 1 W of AI power, averaged over a step. Active steps are split into thirds at the device's own 33rd and 67th percentiles (light / moderate / heavy), so "heavy" means heavy for that machine. Forecast steps are labeled with the same cut points.

**Bill.** Each forecast step's kWh is multiplied by the rate of the hour it falls in, so the steps add up to the bill. On `TARIFF=pop`, peak and off-peak hours come from the backend's own `cheap_hours.py`. The projected bill adds `BASELINE_BILL`, the AI cost measured so far this cycle, and the forecast for the time left.

Ranges are 80%, from 500 simulated futures per agent, so a total has its own range instead of a sum of each step's. Simulated futures only vary step to step around the learned routine and don't know the routine itself may be off. So a total's range is never narrower than the backtest's error on the totals of the held-out windows.

## Data

| Source | Where | Notes |
|---|---|---|
| IEMOP RTD Regional Summaries | iemop.ph → Market Data, public, no login | Daily `RTDREG_YYYYMMDD.csv`, 5-minute intervals. Luzon = `REGION_NAME CLUZ`, `COMMODITY_TYPE En`, demand = `MKT_REQT` (MW). The interval ending at midnight is written as a bare date. The public page keeps about 90 days, so re-run step 1 every few weeks to build a longer history. |
| Device readings | `backend/.env` database, tables `samples` and `ai_samples` | Needs at least **2 known hours** to fine-tune (`device.min_hours`). That is enough to fit, not to know the device's day: see [15-minute steps](#15-minute-steps). Two weeks or more is better, because the weekly routine needs each hour of the week seen at least twice. |

**Time the reader didn't run** (`device.gaps` in `config.json`, or `--gaps` on the export script):

| Value | Rule |
|---|---|
| `day` (default) | On a day the reader ran at least an hour, steps without readings count as no AI use (computer off or asleep), as in the backend's daily totals. A day with no readings is unknown. |
| `missing` | Only steps the reader ran at least half of count, scaled to the full step. Everything else is unknown. |
| `zero` | Every step without readings counts as no AI use. |

Unknown steps are missing values for the model, not zeros. The Kalman filter handles them.

## What's committed

- **Committed:** code, the notebook (without outputs), and `artifacts/luzon/` (from public data).
- **Ignored:** `data/` (downloads and exports), `artifacts/luzon/checkpoints/` (re-created by training), and `artifacts/devices/`, which describes one person's computer use.

## Using it in the app

`/api/forecast` uses the model on its own (`backend/app/services/arima_forecast.py`). It loads this computer's `artifacts/devices/device_<id>_model.json`, runs `wattcast.pipeline.forecast` on the latest readings (no refitting; reused for 5 minutes), and takes the rest of the billing cycle from it in place of the trend, with an 80% range (`forecast_range`). The months after the cycle stay on the trend. The response's `method` says which forecast the bill is on and why.

`ARIMA_FORECAST` in `backend/.env` decides when: `auto` (default) only when `beats_baselines` is true in the model file, `on` whenever there is one (to try it out), `off` never. `ARIMA_MODEL_DIR` moves the folder it reads. A retrained model is picked up on the next request.

Refit daily while the device has under a week of readings, then weekly, or whenever a backtest score drifts.
