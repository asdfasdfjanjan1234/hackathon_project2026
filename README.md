# ⚡ WATT-TRACE SCADA // AI Wattage & Carbon Telemetry

Measures physical electricity consumption of AI models, forecasts utility bills, tracks carbon footprints, and recommends power-saving load directives.

* 📘 **[Hackathon Presentation & Architecture Guide](HACKATHON_PITCH_AND_DOCS.md)** (3-minute pitch script, innovation pillars, and API docs).
* 📋 **[Full Project Plan & Specifications](PROJECT_PLAN.md)**.

## Structure

```
backend/                  Flask API (port 5001)
  run.py                  Entry point
  collect.py              Device collector (run while using AI tools)
  demo_load.py            Keeps an Ollama model busy for the live demo; follows applied switches
  preflight.py            Checks a machine is demo-ready: sensors, nvidia-smi, Ollama, database (PASS/WARN/FAIL)
  migrate_to_mysql.py     Copies readings from the SQLite file into MySQL
  db/setup_mysql.sql      Creates the MySQL database and user
  app/
    __init__.py           App factory
    config.py             Rate, baseline bill, budget (from .env)
    routes/               API endpoints
      usage.py            GET /api/usage            kWh + cost per model
                          GET /api/usage/log        timestamped records (IDE, app, model, effort, watts) and totals by each
      live.py             GET /api/live             current watts
      forecast.py         GET /api/forecast         projected monthly bill
      recommendations.py  GET /api/recommendations  STOP / SWITCH / REDUCE tips, with CO₂ saved each
      carbon.py           GET /api/carbon           CO₂ on device + data center, cycle/year, carbon budget
      best_time.py        GET /api/best-time        cheapest hours on the tariff, cleanest on the grid, best window
      system.py           GET /api/system           detected OS and devices, sensor per component, kWh per component
      device.py           POST /api/device/start|stop, GET /api/device/status, POST /api/device/source
      readings.py         GET /api/devices, GET /api/readings   stored devices and readings
      models.py           GET /api/models           models found in app logs: tokens, estimated data-center Wh
      actions.py          POST /api/actions/apply, GET /api/actions/state   apply a recommendation to Ollama
      alerts.py           GET /api/alerts           budget overruns, savings and notes, most urgent first
      assistant.py        GET /api/assistant/status, POST /api/assistant/chat|warm|pull   the local assistant
      validation.py       GET /api/validation, POST /api/validation/watts|start|finish   wall-meter checks
      health.py           GET /api/health
    services/             Logic, separate from routes
      system_info.py      Detects OS and devices: CPU, RAM, GPUs, NPU, disks, displays, battery
      measurement.py      Picks sensors for the detected OS; watts per CPU / GPU / memory / disk; nvidia-smi
      sensors_macos.py    macOS: battery (ioreg), GPU % and GPU energy (IOReport), powermetrics
      sensors_windows.py  Windows: battery rate, Energy Meter Interface (RAPL), GPU engine counters per process
      sensors_linux.py    Linux: battery (sysfs), RAPL powercap, AMD GPU (amdgpu)
      ai_processes.py     Finds AI apps / local model runners and their CPU, memory and process IDs
      local_models.py     Which models Ollama / LM Studio have loaded or installed (one row per Ollama runner)
      attribution.py      Fits watts ≈ idle + a·CPU% + b·GPU%; splits measured CPU/GPU power per app
      collector.py        Sampling loop used by collect.py and the device reader
      device_reader.py    Runs the collector in a background thread ("Start reading my device")
      model_usage.py      Reads Claude Code / Codex / Copilot logs → tokens per model per day
      storage.py          MySQL or SQLite storage of devices and readings
      models_catalog.py   Local models (watts) and cloud models (list prices → data-center Wh estimate)
      usage_store.py      Daily usage per model from this device's readings
      forecasting.py      Billing cycle, weekday/weekend pattern, damped trend → bill per day and 1/3/12 months
      recommendations.py  Rule-based recommendations with savings (budget, smaller model, quantization, idle, …)
      carbon.py           CO₂ per model and day, two grid factors, carbon budget, CO₂ avoided by recommendations
      clean_hours.py      Hourly grid CO₂ (Electricity Maps) → cleanest window to run batch AI jobs
      cheap_hours.py      Flat or Meralco Peak/Off-Peak tariff → cheapest hours, and the best of price and CO₂
      outlook.py          Forecast + recommendations together ("with recommendations" path); snapshot of every view
      alerts.py           Rule-based alerts from the snapshot (works without the assistant)
      assistant.py        Kilo: dashboard figures as text, prompt, streaming replies from Ollama
      actions.py          Unloads / switches Ollama models when a recommendation is applied
      validation.py       Compares our whole-machine readings with a plug-in wall meter
      usage_log.py        Usage records and their energy by date, IDE, app, model and effort
  tests/                  API, measurement, sensors, storage, forecast, recommendations, platforms (Linux/Windows/NVIDIA/Ollama)

frontend/                 React + Vite (port 5173), proxies /api to Flask
  src/
    App.jsx               Dashboard layout
    api/client.js         API calls
    components/           LiveWattage, BillSummary, UsageBreakdown, UsageLog (records and the formula),
                          ForecastChart, Recommendations, CarbonFootprint, MeterCheck (wall-meter
                          check), ScaleUp (monthly / team projection)
```

## Run it

Backend (terminal 1):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Frontend (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Read this device

Click **Start reading my device** at the top of the dashboard. The backend, running on your own computer, then:

1. detects the OS and hardware (CPU, GPU, NPU, RAM, disks, battery) and picks a sensor for each part,
2. finds the AI apps running (Claude Code, Codex, Copilot, Ollama, …), the host they run in (VS Code, Terminal) and the commands agents run for you ("tool runs"),
3. reads which models they used from their local logs (Claude Code transcripts, Codex sessions, Copilot logs): model names and token counts only, never prompts or code,
4. measures watts every 2 seconds into the database (MySQL, or `backend/data/wattage.db`) until you click **Stop reading**.

The dashboard shows this device's readings. A browser can't read hardware or local files, which is why the backend has to run on the computer being measured.

`python collect.py` (in `backend/`, with the venv active) does the same from a terminal. The dashboard picks up its readings too. On startup it first detects the OS and devices, then lists the sensor it will use for each part (`~` in the readings marks an estimate):

```text
Detected macos 27.0.1 (arm64) on a laptop: MacBook Air (Mac14,2)
  CPU       Apple M2, 8 cores, 16.0 GB RAM
  GPU       Apple M2 (integrated)
  NPU       Apple Neural Engine
  Disks     APPLE SSD AP0256Z (nvme, 251 GB)
  Displays  Color LCD (built-in)
  Battery   66%, on battery
Power readings:
  system    battery (ioreg)
  cpu       estimated
  gpu       IOReport GPU Energy
  memory    estimated
  disk      estimated
```

The same information is at `GET /api/system`. Detection uses `platform` and `psutil` on every OS, plus `system_profiler` on macOS and PowerShell CIM queries on Windows; no extra packages. See [PROJECT_PLAN.md §2](PROJECT_PLAN.md#2-measurement-from-device-resources) for what each OS can measure.

### Database (MySQL)

Readings go to a local SQLite file by default. To store them in MySQL instead:

```bash
mysql -u root -p < backend/db/setup_mysql.sql      # creates the ai_wattage database and a wattage user
# backend/.env:
DATABASE_URL=mysql://wattage:change-me@localhost:3306/ai_wattage
cd backend && python migrate_to_mysql.py          # optional: copy readings already in wattage.db
```

The backend creates the tables on first connect:

| Table | One row per |
|---|---|
| `devices` | computer that took readings (machine ID, hostname, OS, model, CPU, RAM) |
| `samples` | 2-second reading: CPU %, GPU %, estimated and measured watts |
| `component_samples` | component in a reading: cpu / gpu / memory / disk / other watts and its sensor |
| `ai_samples` | AI app in a reading: timestamp, seconds covered, app, model, host (IDE or terminal), effort, CPU %, memory, attributed watts |
| `power_windows` | averaged battery-sensor window used to fit the power model |
| `settings` | stored values, e.g. the fitted power model |
| `meter_checks` | check against a wall meter: meter reading, our reading, when |

Every reading row has the `device_id` of the computer that took it. `GET /api/devices` lists the devices; `GET /api/readings?device_id=&since=&until=&limit=` returns stored readings with their components and AI apps.

### Usage log and the energy formula

The **Usage log** view (`GET /api/usage/log?range=7d|30d|month&slot=60|900|3600`, add `&format=csv` for a file) lists the records behind every figure: when, in which IDE, which AI app, which model, at what reasoning effort, and the watts. Each `ai_samples` row is one AI app in one reading, with the watts attributed to it `P` and the seconds since the previous reading `Δt` (about 2). A record in the log adds up the readings that share a time slot, IDE, app, model and effort.

Energy is watts added up over time. For any group of readings `G` (a date, an IDE, a model, an effort level, or a combination):

```
E_G (Wh)   = Σ_{i ∈ G} P_i · Δt_i / 3600          watts × seconds = joules; 3600 J = 1 Wh
E_G (kWh)  = E_G (Wh) / 1000
P̄_G (W)    = Σ_{i ∈ G} P_i · Δt_i / Σ_{i ∈ G} Δt_i   time-weighted average watts
Cost_G     = E_G (kWh) × rate

P_i = P_cpu,i + P_gpu,i + P_memory,i               the app's share of the machine's power above idle
```

Example: Claude Code at an average 6 W for 30 minutes is 6 × 1800 / 3600 = 3 Wh = 0.003 kWh, or ₱0.036 at ₱12/kWh.

Every reading belongs to exactly one date, one IDE, one app, one model and one effort level, so each breakdown adds up to the same total (a test checks this). Time and average watts are per app: two apps running for the same hour count two hours. `P_i` is what the app drew on this device (see [PROJECT_PLAN.md §2](PROJECT_PLAN.md#2-measurement-from-device-resources) for how watts are attributed); a cloud model's own inference runs in the provider's data center and is estimated separately at `GET /api/models`. Effort is read from the app's own logs and is empty for apps that don't record one.

Tests: `cd backend && .venv/bin/python -m pytest` (add `TEST_DATABASE_URL=mysql://…/ai_wattage_test` to also run the storage tests on MySQL)

### Check the readings against a wall meter

Plug the computer into a plug-in power meter or a smart plug that shows watts, start the device reader, and open **This Device → Wall-Meter Check**:

- **Spot check:** hold the load steady for 30 s and type the watts the meter shows. It's compared with our average over those 30 s.
- **Energy check:** type the meter's kWh counter, run any workload, and type it again at the end. Meters count in 0.01 kWh steps, so a laptop needs an hour or more; a gaming PC needs a few minutes.

The panel shows the average difference over all checks. That's the accuracy figure to quote. The meter reads at the wall, so it also counts charger losses (often 5–15%) and battery charging; keep a laptop at 100%.

### Apply a recommendation live

When a recommendation's model is loaded in Ollama, it gets an **Unload now** or **Switch now** button. Unload frees the model with `keep_alive: 0`. Switch unloads the big model, loads the smaller one, and records the switch at `GET /api/actions/state`. The card then shows the AI watts before and now.

The app can't change which model your other tools ask for. For the demo, `demo_load.py` stands in for the user: it keeps prompting a model and follows the switch.

```bash
cd backend && .venv/bin/python demo_load.py --model llama3:70b
```

### Ask Kilo (on-device assistant)

Kilo explains the dashboard in plain words (English, Filipino or Taglish) and speaks up when something needs attention. It runs on a small model in [Ollama](https://ollama.com) on the same computer, so no question or reading leaves it.

```bash
brew install ollama && brew services start ollama   # Windows/Linux: installer from ollama.com
ollama pull qwen3.5:4b-q4_K_M                       # 3.3 GB; or use "Download" in the Kilo panel
```

- **Ask:** the **Ask Kilo** button (bottom right), the suggested questions, or the mic (Chrome and Safari; Chrome sends the audio to Google for recognition). Spoken questions get spoken answers; the speaker icon reads every reply aloud.
- **Speaks up by itself:** when a new alert appears (over budget, over the carbon budget, a saving), Kilo explains it in a bubble over the button, aloud if voice is on, and as a desktop notification if you turned those on. The bell lists all alerts, each with **Ask Kilo**.
- **Numbers come from the backend, not the model:** `services/assistant.py` turns every view's figures into text with their units, and the prompt tells the model to copy them. A 4B model still slips sometimes, so the panel says to check figures on the dashboard.
- **Model:** `qwen3.5:4b-q4_K_M` by default (about 21 tokens/s on an M2 with 16 GB). In our tests it was more accurate than `gemma4:e2b-it-qat`, which is about 1.7× faster but misread the figures more often. Change `ASSISTANT_MODEL` in `.env`. Kilo's own energy is measured like any local model's (`Ollama · qwen3.5:4b-q4_K_M` in Model Runtimes).

## Notes

- **Your bill:** set the rate, baseline bill, this month's bill, budget and billing-cycle start day in Tariff & Hardware. The backend does all bill math with them.
- **Comparisons:** CO₂ uses the Philippine DOE grid emission factor (0.7122 kg/kWh, Luzon-Visayas) and "hours of aircon" a 1 HP non-inverter unit (750 W). Change `GRID_CO2_KG_PER_KWH` and `AIRCON_WATTS` in `.env` for other places.
- **Live power on Mac:** no sudo needed. The battery sensor gives measured system power on Apple Silicon laptops, and IOReport gives measured GPU power. Desktop Macs have no battery sensor.
- **Live power on Windows:** no extra installs. Battery power while unplugged, and CPU/GPU/RAM energy where the PC exposes the Energy Meter Interface. GPU use is read per process and per engine (3D, Compute, CUDA). Not yet tested on a real Windows PC.
- **Live power on Linux:** battery power while unplugged, RAPL CPU/iGPU/RAM energy (most distributions allow this for root only; otherwise it's estimated), AMD GPU power and utilization. Tested against sample sysfs files only.
- **NVIDIA GPUs (any OS):** `nvidia-smi` gives measured GPU watts and utilization, and which processes run GPU compute, so a game isn't counted as local AI.
- **Accuracy:** where a CPU or GPU power sensor exists, each app gets its share of the *measured* power above idle; otherwise the fitted formula. Until it's fitted, defaults depend on the device (Apple Silicon, laptop or desktop).
- **Port 5001**, not 5000, because macOS uses 5000 for AirPlay Receiver.
