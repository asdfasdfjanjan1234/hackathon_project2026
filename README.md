# AI Wattage Tracker

Measures how much electricity AI models use, forecasts the electricity bill, and recommends ways to reduce it. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full idea.

## Structure

```
backend/                  Flask API (port 5001)
  run.py                  Entry point
  app/
    __init__.py           App factory
    config.py             Rate, baseline bill, budget (from .env)
    routes/               API endpoints
      usage.py            GET /api/usage            kWh + cost per model
      live.py             GET /api/live             current watts
      forecast.py         GET /api/forecast         projected monthly bill
      recommendations.py  GET /api/recommendations  STOP / SWITCH / REDUCE tips
      health.py           GET /api/health
    services/             Logic, separate from routes
      measurement.py      Reads watts (powermetrics / nvidia-smi, else simulated)
      models_catalog.py   Known models, local vs cloud, power/energy figures
      usage_store.py      Daily usage per model (sample data for now)
      sample_data.py      Generates 30 days of realistic demo data
      forecasting.py      Linear trend → monthly bill forecast
      recommendations.py  Rule-based recommendations with savings
  tests/test_api.py

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

Tests: `cd backend && .venv/bin/python -m pytest`

## Notes

- **Sample data:** `USE_SAMPLE_DATA=true` in `backend/.env` runs the app on generated data. Real usage storage is still to be built.
- **Live power on Mac:** `powermetrics` needs sudo. Until a privileged collector is built, `/api/live` returns simulated values and the dashboard labels them "simulated".
- **Port 5001**, not 5000, because macOS uses 5000 for AirPlay Receiver.
