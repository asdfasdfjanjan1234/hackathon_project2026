# Technical disclosure

Every model, library, service and outside asset Kilo What? uses, where each one runs, and what the app can't do yet ([Limitations](#limitations)). The dashboard shows the same under **About → Technical disclosure** (`frontend/src/disclosure.js`); change both together.

Everything the dashboard shows is computed on the computer being measured. Kilo What? calls no hosted LLM API and no paid cloud service. All project code was written for this hackathon (first commit 9 October 2026).

## Models

| Model | Runs with | What it does | Where it runs |
|---|---|---|---|
| `qwen3.5:4b-q4_K_M` | Ollama | Kilo, the assistant: explains the dashboard's figures and answers questions in English, Filipino or Taglish. Default; set by `ASSISTANT_MODEL` in `backend/.env` | This device |
| `gemma4:e2b-it-qat` | Ollama | Tested as Kilo's model: about 1.7× faster, but misread the figures more often. Not the default | This device |
| ARIMA, one per AI agent | statsmodels (SARIMAX) | Forecasts each agent's energy in 15-minute steps; their sum is the AI part of the projected bill. Pre-trained on IEMOP Luzon demand, fine-tuned on the device's own readings | This device |
| Damped trend | Python | Bill forecast from the weekday/weekend pattern while no ARIMA is fitted yet | This device |
| Power model: watts ≈ idle + a·CPU% + b·GPU% | NumPy (non-negative least squares) | Splits the machine's measured watts across the AI apps running. Fitted per device | This device |
| `llama3.1:8b`, `llama3:70b` | Ollama | Workload for the live demo (`backend/demo_load.py`). Not part of the product | Team only |
| Kokoro v1.0, voice `af_heart` | kokoro-onnx | Narration for the promo videos | Team only |

## Python libraries

| Package | Version | Part | What we use it for |
|---|---|---|---|
| Flask | 3.1.0 | Backend | The REST API the dashboard reads |
| flask-cors | 5.0.0 | Backend | Lets the dashboard call the API |
| python-dotenv | 1.0.1 | Backend | Reads rate, bill and budget settings from `backend/.env` |
| psutil | 6.1.1 | Backend | CPU, memory, battery and process readings; finds the AI apps running |
| NumPy | 2.2.1 | Backend | Power model fit (non-negative least squares) and forecast math |
| pandas | 2.2.3 | Backend | Time series for the ARIMA forecast |
| statsmodels | 0.14.4 | Backend | ARIMA (SARIMAX) models |
| SciPy | 1.14.1 | Backend | Required by statsmodels (1.15 fails to load on recent macOS) |
| holidays | 0.62 | Backend | Philippine public holidays as a forecast input |
| PyMySQL | 1.1.1 | Backend | Optional MySQL storage |
| cryptography | 44.0.0 | Backend | MySQL 8 sign-in for PyMySQL |
| pytest | 8.3.4 | Backend | Backend and training tests |
| matplotlib | 3.9.2 | Training | Charts in the forecast notebook |
| ipykernel | 6.29.5 | Training | Notebook kernel for VS Code / Jupyter |
| kokoro-onnx | Not pinned | Promo | Text-to-speech narration |
| espeakng-loader | Not pinned | Promo | Phonemes for kokoro-onnx |
| soundfile | Not pinned | Promo | Reads and writes the audio tracks |
| imageio-ffmpeg | Not pinned | Promo | ffmpeg for mixing and encoding the videos |
| Playwright | Not pinned | Promo | Screenshots of the running dashboard in headless Chrome |

Backend versions are pinned in `backend/requirements.txt`, training versions in `training/arima_forecast/requirements.txt`. From Python's standard library: `sqlite3` (the default database), `ctypes` and `winreg` (Windows sensors), `subprocess` (OS tools and `nvidia-smi`), `urllib` (Ollama and Electricity Maps), `threading` (the device reader).

## Tech stack

| Layer | Technologies |
|---|---|
| Languages | Python 3.10+ (tested on 3.10.11), JavaScript (ES modules) |
| Frontend | React 18.3.1, Vite 6.4.4, Tailwind CSS 3.4.19, Recharts 2.15.4, Lucide 1.54.0, PostCSS 8.5.29, Autoprefixer 10.6.1 (installed versions, `package-lock.json`) |
| Backend | Flask 3.1.0 on 127.0.0.1:5001; Vite proxies `/api` to it |
| Database | SQLite file by default (`backend/data/wattage.db`); MySQL optional |
| Local AI runtime | Ollama on 127.0.0.1:11434 (Kilo, one-click model switch); LM Studio read for loaded models |
| Sensors: macOS | `ioreg` (battery), IOReport (GPU energy), `powermetrics`, `system_profiler` |
| Sensors: Windows | Energy Meter Interface (RAPL), PowerShell CIM, GPU engine performance counters |
| Sensors: Linux | sysfs powercap (RAPL), battery, amdgpu |
| Sensors: NVIDIA | `nvidia-smi` on any OS: GPU watts, utilization, compute processes |
| Browser APIs | Web Speech API (listening and speaking), Notifications API |
| Promo videos | Playwright with headless Chrome, ffmpeg, kokoro-onnx; macOS `say` as the fallback voice |

## APIs and online services

| Service | Used for | Needed | What leaves this computer | Without it |
|---|---|---|---|---|
| [Electricity Maps API](https://api.electricitymap.org/v3/carbon-intensity) | Hourly grid CO₂ for the Luzon zone (`PH-LU`), for the cleanest hours to run batch AI jobs | Optional (`ELECTRICITYMAPS_TOKEN`) | Zone code and your API token | CO₂ uses the fixed DOE grid factor |
| Google speech recognition (through Chrome) | Spoken questions to Kilo | Optional | Your spoken audio, sent by Chrome | Type the question |
| Google Fonts | DM Sans in the dashboard | Optional | A font request | A system font |
| Ollama model registry | Downloading Kilo's model (3.3 GB) | Setup only | The model name | Kilo stays off |
| [IEMOP market data](https://www.iemop.ph/market-data/rtd-regional-summaries/) | Luzon demand for pre-training the forecast | Training only | Nothing but the download request | Rebuild from files already downloaded (`--offline`) |

Cloud AI tools you run yourself (Claude Code, Copilot, Codex) use the internet on their own; Kilo What? only reads their local logs.

## Existing assets and data

- **App and tool logos:** 46 SVGs in `frontend/public/brands/` label the AI apps, IDEs and terminals the device reader finds. Some come from LobeHub's lobe-icons. Each is a trademark of its owner.
- **DM Sans:** font under the SIL Open Font License, from Google Fonts in the app and bundled in `promo/assets/fonts/`.
- **Grid emission factor:** Philippine DOE factor, 0.7122 kg CO₂ per kWh (Luzon-Visayas).
- **Meralco tariff:** flat rate or Peak/Off-Peak structure, with the rates from the user's own bill.
- **Cloud model list prices:** public per-token prices, used to estimate a cloud model's data-center energy.
- **AI app logs on this device:** Claude Code transcripts, Codex sessions and Copilot logs: model names and token counts only, never prompts or code.
- **Kokoro voice files:** `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0), used only to render the promo videos.

The open-source libraries above are used under their own licenses.

## Limitations

What the numbers can't tell you, and what isn't finished. The dashboard labels every estimated figure as estimated.

### Measurement

- **Whole-machine watts need a battery sensor.** Mac laptops report them all the time, Windows laptops only while unplugged. Desktops and plugged-in Windows PCs have no whole-machine reading, so the total is built from the parts.
- **Some parts are always estimated.** Disk on every OS. CPU and RAM on a Mac, because their sensors need root. RAM on most Windows PCs, because the RAPL DRAM channel is mostly on server CPUs.
- **Watts per app are calculated, not measured.** The machine's measured power above idle is split by each app's CPU and GPU share, using a formula fitted to this device. Until about 8 battery readings are in, it uses defaults for the device type. Idle power is never counted as AI.
- **AI extensions inside VS Code's shared extension host can't be measured on their own.** Only tools that start their own process can, such as Claude Code, Copilot's runtime and Codex.
- **Loaded models can share one number.** LM Studio's use is split between its loaded models by size, not by which one is generating. Older Ollama versions that run models inside the server process give all of it to the most recently used model.
- **Only time with the reader running counts.** Readings are taken while **Start reading my device** or `collect.py` runs. AI use while it's stopped isn't recorded.
- **Windows and Linux sensors are less tested than macOS.** The Windows readers follow Microsoft's documentation and are tested against sample output; Linux only against sample sysfs files. A sensor that fails or is denied falls back to an estimate.
- **No accuracy figure yet.** The wall-meter check is built, but we haven't recorded enough checks to quote an accuracy. A wall meter also counts charger losses (often 5–15%) and battery charging.

### Cloud AI

- **Data-center energy ranks models; it doesn't measure them.** Providers don't publish energy per model. We scale each model's list price per token to one published figure (Epoch AI, about 0.3 Wh per typical GPT-4o query). Price includes margin and business choices, so a cheaper newer model is estimated lower. This energy isn't on the user's bill.
- **Token counts come from some apps only.** Exact for Claude Code, Codex, OpenCode and Gemini CLI. Copilot, Kiro and Amazon Q logs name the model but give no tokens, so those get no data-center estimate. Claude Desktop, the ChatGPT app and Cursor store nothing readable, so their model is unknown.
- **Device readings can't tell cloud models apart.** The laptop looks the same whether Claude Code uses Opus or Sonnet. Each reading goes to the model of the app's most recent response, from the log timestamps.

### Forecast

- **A short history gives a rough forecast.** The ARIMA is pre-trained on Luzon grid demand, then fine-tuned on this device's readings. An hour of the day it hasn't seen yet is forecast at the device's average, so the rest of the cycle stays rough until it has seen whole days. Before 2 hours of readings, the damped-trend fallback is used.
- **Made-up history counts as real until it's removed.** `backend/seed_history.py` can add made-up days before the first real reading, so the forecast has something to learn from. The dashboard's history, usage and forecast count those rows, and so do the accuracy scores of a model fitted on them. Nothing on screen marks them. `python seed_history.py --remove` deletes them.

### Bill, tariff and carbon

- **One computer at a time.** The backend has to run on the computer it measures, because a browser can't read hardware. The bill impact counts only this computer's AI. "Other usage" is whatever the rate change and AI don't explain (aircon, appliances); it isn't measured. The team figures in **If You Kept This Up** multiply this computer's figures.
- **Built for the Philippines.** Pesos, Meralco's flat or Peak/Off-Peak tariff, the DOE grid factor and Luzon demand for pre-training. Other tariff structures aren't modelled. Peak/Off-Peak rates are estimated from the regular rate unless set from a bill, and public holidays aren't modelled. Elsewhere, change the rate and `GRID_CO2_KG_PER_KWH` in `backend/.env`.
- **One CO₂ factor for every hour.** CO₂ totals use the DOE factor (0.7122 kg per kWh) all day. Hourly grid CO₂ for **Cleanest Hours** needs an Electricity Maps token; without one that card stays empty. Data-center CO₂ carries the cloud estimate's uncertainty.

### Kilo and one-click fixes

- **Kilo can get a figure wrong.** It's a 4B model on this computer. The backend hands it every figure as text, but it still slips sometimes, so the panel says to check figures on the dashboard. It needs Ollama and a 3.3 GB model; without them Kilo stays off and the rest of the dashboard works.
- **Voice depends on the browser.** Spoken questions work in Chrome and Safari only, and Chrome sends the audio to Google.
- **Fixes apply to Ollama only.** **Unload now** and **Switch now** act on models loaded in Ollama. The app can't change which model Claude Code, Copilot or LM Studio asks for; the user has to. In the demo, `demo_load.py` stands in for the user.

## AI development tools

- **Claude Code (Anthropic):** wrote and edited code, tests and docs; `AGENTS.md` holds its project instructions.
