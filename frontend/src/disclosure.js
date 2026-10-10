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

export const DEV_TOOLS = [
  {
    name: "Claude Code (Anthropic)",
    use: "Wrote and edited code, tests and docs; AGENTS.md holds its project instructions.",
  },
];
