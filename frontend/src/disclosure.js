// What Kilo What? is built with, for the Technical disclosure view. TECHNICAL_DISCLOSURE.md at the
// repo root says the same; change both together. Versions are the pinned ones (requirements.txt,
// package-lock.json).

// `where`: "device" runs on the computer being measured; "team" ran only on the team's computers.
export const MODELS = [
  {
    name: "qwen3.5:4b-q4_K_M",
    runtime: "Ollama",
    use: "Kilo, the assistant: explains the dashboard's figures and answers questions in English, Filipino or Taglish.",
    where: "device",
    note: "Default. Set by ASSISTANT_MODEL in backend/.env.",
  },
  {
    name: "gemma4:e2b-it-qat",
    runtime: "Ollama",
    use: "Tested as Kilo's model. About 1.7× faster, but misread the figures more often.",
    where: "device",
    note: "Not the default.",
  },
  {
    name: "ARIMA, one per AI agent",
    runtime: "statsmodels (SARIMAX)",
    use: "Forecasts each agent's energy in 15-minute steps; their sum is the AI part of the projected bill.",
    where: "device",
    note: "Pre-trained on IEMOP Luzon demand, fine-tuned on this device's readings.",
  },
  {
    name: "Damped trend",
    runtime: "Python",
    use: "Bill forecast from the weekday/weekend pattern while no ARIMA is fitted yet.",
    where: "device",
    note: "Fallback.",
  },
  {
    name: "Power model: watts ≈ idle + a·CPU% + b·GPU%",
    runtime: "NumPy (non-negative least squares)",
    use: "Splits the machine's measured watts across the AI apps running.",
    where: "device",
    note: "Fitted per device.",
  },
  {
    name: "llama3.1:8b, llama3:70b",
    runtime: "Ollama",
    use: "Workload for the live demo (demo_load.py). Not part of the product.",
    where: "team",
    note: "Demo only.",
  },
  {
    name: "Kokoro v1.0, voice af_heart",
    runtime: "kokoro-onnx",
    use: "Narration for the promo videos.",
    where: "team",
    note: "Promo only.",
  },
];

export const PYTHON_LIBRARIES = [
  { name: "Flask", version: "3.1.0", part: "Backend", use: "The REST API the dashboard reads" },
  { name: "flask-cors", version: "5.0.0", part: "Backend", use: "Lets the dashboard call the API" },
  { name: "python-dotenv", version: "1.0.1", part: "Backend", use: "Reads rate, bill and budget settings from backend/.env" },
  { name: "psutil", version: "6.1.1", part: "Backend", use: "CPU, memory, battery and process readings; finds the AI apps running" },
  { name: "NumPy", version: "2.2.1", part: "Backend", use: "Power model fit (non-negative least squares) and forecast math" },
  { name: "pandas", version: "2.2.3", part: "Backend", use: "Time series for the ARIMA forecast" },
  { name: "statsmodels", version: "0.14.4", part: "Backend", use: "ARIMA (SARIMAX) models" },
  { name: "SciPy", version: "1.14.1", part: "Backend", use: "Required by statsmodels (1.15 fails to load on recent macOS)" },
  { name: "holidays", version: "0.62", part: "Backend", use: "Philippine public holidays as a forecast input" },
  { name: "PyMySQL", version: "1.1.1", part: "Backend", use: "Optional MySQL storage" },
  { name: "cryptography", version: "44.0.0", part: "Backend", use: "MySQL 8 sign-in for PyMySQL" },
  { name: "pytest", version: "8.3.4", part: "Backend", use: "Backend and training tests" },
  { name: "matplotlib", version: "3.9.2", part: "Training", use: "Charts in the forecast notebook" },
  { name: "ipykernel", version: "6.29.5", part: "Training", use: "Notebook kernel for VS Code / Jupyter" },
  { name: "kokoro-onnx", version: "Not pinned", part: "Promo", use: "Text-to-speech narration" },
  { name: "espeakng-loader", version: "Not pinned", part: "Promo", use: "Phonemes for kokoro-onnx" },
  { name: "soundfile", version: "Not pinned", part: "Promo", use: "Reads and writes the audio tracks" },
  { name: "imageio-ffmpeg", version: "Not pinned", part: "Promo", use: "ffmpeg for mixing and encoding the videos" },
  { name: "Playwright", version: "Not pinned", part: "Promo", use: "Screenshots of the running dashboard in headless Chrome" },
];

export const PYTHON_STDLIB =
  "sqlite3 (the default database), ctypes and winreg (Windows sensors), subprocess (OS tools and nvidia-smi), " +
  "urllib (Ollama and Electricity Maps), threading (the device reader)";

export const STACK = [
  { layer: "Languages", items: "Python 3.10+ (tested on 3.10.11), JavaScript (ES modules)" },
  { layer: "Frontend", items: "React 18.3.1, Vite 6.4.4, Tailwind CSS 3.4.19, Recharts 2.15.4, Lucide 1.54.0, PostCSS 8.5.29, Autoprefixer 10.6.1" },
  { layer: "Backend", items: "Flask 3.1.0 on 127.0.0.1:5001; Vite proxies /api to it" },
  { layer: "Database", items: "SQLite file by default (backend/data/wattage.db); MySQL optional" },
  { layer: "Local AI runtime", items: "Ollama on 127.0.0.1:11434 (Kilo, one-click model switch); LM Studio read for loaded models" },
  { layer: "Sensors: macOS", items: "ioreg (battery), IOReport (GPU energy), powermetrics, system_profiler" },
  { layer: "Sensors: Windows", items: "Energy Meter Interface (RAPL), PowerShell CIM, GPU engine performance counters" },
  { layer: "Sensors: Linux", items: "sysfs powercap (RAPL), battery, amdgpu" },
  { layer: "Sensors: NVIDIA", items: "nvidia-smi on any OS: GPU watts, utilization, compute processes" },
  { layer: "Browser APIs", items: "Web Speech API (listening and speaking), Notifications API" },
  { layer: "Promo videos", items: "Playwright with headless Chrome, ffmpeg, kokoro-onnx; macOS say as the fallback voice" },
];

// `needed`: when the service is used at all. `sends`: what leaves the computer.
export const SERVICES = [
  {
    name: "Electricity Maps API",
    use: "Hourly grid CO₂ for the Luzon zone (PH-LU), for the cleanest hours to run batch AI jobs",
    needed: "Optional",
    sends: "Zone code and your API token",
    without: "CO₂ uses the fixed DOE grid factor",
  },
  {
    name: "Google speech recognition (through Chrome)",
    use: "Spoken questions to Kilo",
    needed: "Optional",
    sends: "Your spoken audio, sent by Chrome",
    without: "Type the question",
  },
  {
    name: "Google Fonts",
    use: "DM Sans in the dashboard",
    needed: "Optional",
    sends: "A font request",
    without: "A system font",
  },
  {
    name: "Ollama model registry",
    use: "Downloading Kilo's model (3.3 GB)",
    needed: "Setup only",
    sends: "The model name",
    without: "Kilo stays off",
  },
  {
    name: "IEMOP market data",
    use: "Luzon demand for pre-training the forecast",
    needed: "Training only",
    sends: "Nothing but the download request",
    without: "Rebuild from files already downloaded (--offline)",
  },
];

export const ASSETS = [
  {
    name: "App and tool logos",
    detail: "46 SVGs in frontend/public/brands/ label the AI apps, IDEs and terminals the device reader finds. Some come from LobeHub's lobe-icons. Each is a trademark of its owner.",
  },
  {
    name: "DM Sans",
    detail: "Font under the SIL Open Font License, from Google Fonts in the app and bundled in promo/assets/fonts/.",
  },
  {
    name: "Grid emission factor",
    detail: "Philippine DOE factor, 0.7122 kg CO₂ per kWh (Luzon-Visayas).",
  },
  {
    name: "Meralco tariff",
    detail: "Flat rate or Peak/Off-Peak structure, with the rates from the user's own bill.",
  },
  {
    name: "Cloud model list prices",
    detail: "Public per-token prices, used to estimate a cloud model's data-center energy.",
  },
  {
    name: "AI app logs on this device",
    detail: "Claude Code transcripts, Codex sessions and Copilot logs: model names and token counts only, never prompts or code.",
  },
  {
    name: "Kokoro voice files",
    detail: "kokoro-v1.0.onnx and voices-v1.0.bin from the kokoro-onnx releases, used only to render the promo videos.",
  },
];

// What the numbers can't tell you, grouped by part of the app.
export const LIMITATIONS = [
  {
    area: "Measurement",
    items: [
      {
        name: "Whole-machine watts need a battery sensor",
        detail: "Mac laptops report them all the time, Windows laptops only while unplugged. Desktops and plugged-in Windows PCs have no whole-machine reading, so the total is built from the parts.",
      },
      {
        name: "Some parts are always estimated",
        detail: "Disk on every OS. CPU and RAM on a Mac, because their sensors need root. RAM on most Windows PCs, because the RAPL DRAM channel is mostly on server CPUs.",
      },
      {
        name: "Watts per app are calculated, not measured",
        detail: "The machine's measured power above idle is split by each app's CPU and GPU share, using a formula fitted to this device. Until about 8 battery readings are in, it uses defaults for the device type. Idle power is never counted as AI.",
      },
      {
        name: "AI extensions inside VS Code's shared extension host can't be measured on their own",
        detail: "Only tools that start their own process can, such as Claude Code, Copilot's runtime and Codex.",
      },
      {
        name: "Loaded models can share one number",
        detail: "LM Studio's use is split between its loaded models by size, not by which one is generating. Older Ollama versions that run models inside the server process give all of it to the most recently used model.",
      },
      {
        name: "Only time with the reader running counts",
        detail: "Readings are taken while Start reading my device or collect.py runs. AI use while it's stopped isn't recorded.",
      },
      {
        name: "Windows and Linux sensors are less tested than macOS",
        detail: "The Windows readers follow Microsoft's documentation and are tested against sample output; Linux only against sample sysfs files. A sensor that fails or is denied falls back to an estimate.",
      },
      {
        name: "No accuracy figure yet",
        detail: "The wall-meter check is built, but we haven't recorded enough checks to quote an accuracy. A wall meter also counts charger losses (often 5–15%) and battery charging.",
      },
    ],
  },
  {
    area: "Cloud AI",
    items: [
      {
        name: "Data-center energy ranks models; it doesn't measure them",
        detail: "Providers don't publish energy per model. We scale each model's list price per token to one published figure (Epoch AI, about 0.3 Wh per typical GPT-4o query). Price includes margin and business choices, so a cheaper newer model is estimated lower. This energy isn't on your bill.",
      },
      {
        name: "Token counts come from some apps only",
        detail: "Exact for Claude Code, Codex, OpenCode and Gemini CLI. Copilot, Kiro and Amazon Q logs name the model but give no tokens, so those get no data-center estimate. Claude Desktop, the ChatGPT app and Cursor store nothing readable, so their model is unknown.",
      },
      {
        name: "Device readings can't tell cloud models apart",
        detail: "The laptop looks the same whether Claude Code uses Opus or Sonnet. Each reading goes to the model of the app's most recent response, from the log timestamps.",
      },
    ],
  },
  {
    area: "Forecast",
    items: [
      {
        name: "A short history gives a rough forecast",
        detail: "The ARIMA is pre-trained on Luzon grid demand, then fine-tuned on this device's readings. An hour of the day it hasn't seen yet is forecast at the device's average, so the rest of the cycle stays rough until it has seen whole days. Before 2 hours of readings, the damped-trend fallback is used.",
      },
      {
        name: "Made-up history counts as real until it's removed",
        detail: "backend/seed_history.py can add made-up days before the first real reading, so the forecast has something to learn from. History, usage and the forecast count those rows, and so do the accuracy scores of a model fitted on them. Nothing on screen marks them. python seed_history.py --remove deletes them.",
      },
    ],
  },
  {
    area: "Bill, tariff and carbon",
    items: [
      {
        name: "One computer at a time",
        detail: "The backend has to run on the computer it measures, because a browser can't read hardware. The bill impact counts only this computer's AI. \"Other usage\" is whatever the rate change and AI don't explain (aircon, appliances); it isn't measured. The team figures in If You Kept This Up multiply this computer's figures.",
      },
      {
        name: "Built for the Philippines",
        detail: "Pesos, Meralco's flat or Peak/Off-Peak tariff, the DOE grid factor and Luzon demand for pre-training. Other tariff structures aren't modelled. Peak/Off-Peak rates are estimated from the regular rate unless set from a bill, and public holidays aren't modelled. Elsewhere, change the rate and GRID_CO2_KG_PER_KWH in backend/.env.",
      },
      {
        name: "One CO₂ factor for every hour",
        detail: "CO₂ totals use the DOE factor (0.7122 kg per kWh) all day. Hourly grid CO₂ for Cleanest Hours needs an Electricity Maps token; without one that card stays empty. Data-center CO₂ carries the cloud estimate's uncertainty.",
      },
    ],
  },
  {
    area: "Kilo and one-click fixes",
    items: [
      {
        name: "Kilo can get a figure wrong",
        detail: "It's a 4B model on this computer. The backend hands it every figure as text, but it still slips sometimes, so the panel says to check figures on the dashboard. It needs Ollama and a 3.3 GB model; without them Kilo stays off and the rest of the dashboard works.",
      },
      {
        name: "Voice depends on the browser",
        detail: "Spoken questions work in Chrome and Safari only, and Chrome sends the audio to Google.",
      },
      {
        name: "Fixes apply to Ollama only",
        detail: "Unload now and Switch now act on models loaded in Ollama. The app can't change which model Claude Code, Copilot or LM Studio asks for; you have to. In the demo, demo_load.py stands in for the user.",
      },
    ],
  },
];

export const DEV_TOOLS = [
  {
    name: "Claude Code (Anthropic)",
    use: "Wrote and edited code, tests and docs; AGENTS.md holds its project instructions.",
  },
];
