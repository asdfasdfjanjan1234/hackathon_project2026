# Technical disclosure

Every model, library, service and outside asset Kilo What? uses, and where each one runs. The dashboard shows the same under **About → Technical disclosure** (`frontend/src/disclosure.js`); change both together.

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

## AI development tools

- **Claude Code (Anthropic):** wrote and edited code, tests and docs; `AGENTS.md` holds its project instructions.
