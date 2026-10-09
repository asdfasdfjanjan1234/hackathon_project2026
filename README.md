# AI Wattage Tracker

Measures how much electricity AI models use, forecasts the electricity bill, and recommends ways to reduce it. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full idea.

## Structure

```
backend/                  Flask API (port 5001)
  run.py                  Entry point
  collect.py              Device collector (run while using AI tools)
  app/
    __init__.py           App factory
    config.py             Rate, baseline bill, budget (from .env)
    routes/               API endpoints
      usage.py            GET /api/usage            kWh + cost per model
      live.py             GET /api/live             current watts
      forecast.py         GET /api/forecast         projected monthly bill
      recommendations.py  GET /api/recommendations  STOP / SWITCH / REDUCE tips
      system.py           GET /api/system           detected OS and devices, sensor per component, kWh per component
      device.py           POST /api/device/start|stop, GET /api/device/status, POST /api/device/source
      models.py           GET /api/models           models found in app logs: tokens, estimated data-center Wh
      health.py           GET /api/health
    services/             Logic, separate from routes
      system_info.py      Detects OS and devices: CPU, RAM, GPUs, NPU, disks, displays, battery
      measurement.py      Picks sensors for the detected OS; watts per CPU / GPU / memory / disk
      sensors_macos.py    macOS: battery (ioreg), GPU % and GPU energy (IOReport), powermetrics
      sensors_windows.py  Windows: battery rate, Energy Meter Interface (RAPL), GPU counters
      ai_processes.py     Finds AI apps / local model runners and their CPU and memory
      attribution.py      Fits watts ≈ idle + a·CPU% + b·GPU%, splits watts per app
      collector.py        Sampling loop used by collect.py and the device reader
      device_reader.py    Runs the collector in a background thread ("Start reading my device")
      model_usage.py      Reads Claude Code / Codex / Copilot logs → tokens per model per day
      storage.py          SQLite storage of samples
      models_catalog.py   Local models (watts) and cloud models (list prices → data-center Wh estimate)
      usage_store.py      Daily usage per model (sample data for now)
      sample_data.py      Generates 30 days of realistic demo data
      forecasting.py      Linear trend → monthly bill forecast
      recommendations.py  Rule-based recommendations with savings
  tests/                  test_api.py, test_measurement.py, test_sensors.py

frontend/                 React + Vite (port 5173), proxies /api to Flask
  src/
    App.jsx               Dashboard layout
    api/client.js         API calls
    components/           LiveWattage, BillSummary, UsageBreakdown,
                          ForecastChart, Recommendations
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
4. measures watts every 2 seconds into `backend/data/wattage.db` until you click **Stop reading**.

The dashboard switches to this device's data; the **This device / Sample (John)** toggle switches back to the demo data. A browser can't read hardware or local files, which is why the backend has to run on the computer being measured.

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

Tests: `cd backend && .venv/bin/python -m pytest`

## Notes

- **Sample data:** `USE_SAMPLE_DATA=true` in `backend/.env` makes the dashboard start on generated data (John's gaming PC); clicking Start reading switches to this device.
- **Your bill:** set the rate, baseline bill, this month's bill and budget in Tariff & Hardware. The backend does all bill math with them.
- **Live power on Mac:** no sudo needed. The battery sensor gives measured system power on Apple Silicon laptops, and IOReport gives measured GPU power. Desktop Macs have no battery sensor.
- **Live power on Windows:** no extra installs. Battery power while unplugged, and CPU/GPU/RAM energy where the PC exposes the Energy Meter Interface. Not yet tested on a real Windows PC.
- **Port 5001**, not 5000, because macOS uses 5000 for AirPlay Receiver.
