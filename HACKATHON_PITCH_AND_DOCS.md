# ⚡ WATT-TRACE SCADA // AI Wattage & Carbon Telemetry

> **Autonomous AI FinOps & Green Computing Telemetry Engine**  
> *Measures physical electricity consumption of local and cloud AI models, forecasts utility bills, tracks carbon footprints, and recommends power-saving load directives.*

---

## 🏆 Hackathon Innovation & Value Proposition

### 1. The Real-World Crisis (2026 AI Era)
As artificial intelligence models (LLMs, coding agents, diffusion models) integrate into every developer and home workstation, electrical grid stress and household utility bills are surging. Consumers and engineering teams face a blind spot:
* **"Did my AI models double my electric bill?"**
* **"How much carbon dioxide is my daily workflow emitting?"**
* **"Which models (Local 70B vs 8B, or Cloud Opus vs Sonnet) are wasting energy?"**

### 2. The Core Innovation: Empirical Systems Telemetry vs Naive Estimation
Most AI cost calculators perform naive token multiplications. **WATT-TRACE SCADA connects directly to OS-level hardware sensors:**
* **Windows Instrumentation**: Energy Meter Interface (EMI / RAPL MSRs), `Win32` CIM power metrics, `nvidia-smi` discrete GPU telemetry, and PDH performance counters.
* **Apple Silicon Instrumentation**: Smart battery controller (`ioreg`), `IOReport` GPU energy channels, and `powermetrics`.
* **Attribution Engine**: Uses **Non-Negative Least Squares (NNLS)** regression to calibrate:
  $$\text{Watts} \approx \text{Idle} + \alpha \cdot \text{CPU}\% + \beta \cdot \text{GPU}\%$$
  Allocates wattage strictly to active AI processes (`ollama`, `lmstudio`, `python`, `claude`) without falsely blaming AI for system idle power.
* **Honest Engineering (Myth-Busting)**:
  * **Local AI Models**: Draw **200W – 600W** on desktop GPUs and **20W – 40W** on laptops. Directly inflates your domestic utility bill.
  * **Cloud AI Models**: Consume data-center power paid by the provider. Home bill impact is negligible ($< \text{₱1/month}$), but Scope 3 data center carbon is tracked via token pricing proxies.

---

## 🎤 3-Minute Hackathon Demo Script (Pitch Guide)

The full script, with setup, checklist, fallbacks and judge Q&A, is in **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)**. Numbers marked **[fill in]** come from rehearsal: never quote a number on stage that we didn't measure.

| Time | Screen | Speaker Dialogue |
|---|---|---|
| **0:00 - 0:42** | **Telemetry Console → This Device** | *"Your electric bill went up. Everyone's saying it's AI. Is it? Most tools guess. We measure: this app reads the laptop's own power sensors and finds every AI app running. Claude Code and Copilot right now: a fraction of a watt. For cloud AI, the honest answer is that it didn't raise your bill."* |
| **0:42 - 1:17** | **Active Power Draw → If You Kept This Up** | *(Start `python demo_load.py --model llama3.1:8b`)* <br>*"But some people run AI on their own machine. There's the model: **[fill in] W**, and the wall meter agrees. Kept up 4 hours a day, that's **₱[fill in]** a month, times ten for a 10-machine dev shop."* |
| **1:17 - 1:40** | **Billing Projection** | *"The app splits the bill increase into the rate change, AI, and everything else. Here AI explains **[fill in]%**."* |
| **1:40 - 2:05** | **Load Directives** | *(Click **Switch now** on the big model)* <br>*"It doesn't just tell you, it fixes it. Big model unloaded, small one loaded: **[fill in] W** down to **[fill in] W**, right now."* |
| **2:05 - 2:35** | **Carbon Ledger → Cleanest Hours; Best Time** | *"It also tells you when to run heavy jobs. Luzon's grid is cleanest **[fill in]**. Moving batch work there avoids **[fill in] g** of CO₂ a month, and on Meralco's Peak/Off-Peak rate those night hours are about ₱2 cheaper per kWh."* |
| **2:35 - 3:00** | **This Device → Wall-Meter Check** | *"Is it accurate? Against a power meter at the wall, within **[fill in]%**, using only the laptop's own sensors. Watt-Trace: the honest answer about AI and your bill, and the fix when it's real."* |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    REACT + VITE FRONTEND                    │
│   (Industrial SCADA UI · Recharts · Lucide · TailwindCSS)   │
└──────────────────────────────▲──────────────────────────────┘
                               │  REST API (Reverse Proxy /api)
┌──────────────────────────────▼──────────────────────────────┐
│                      FLASK BACKEND ENGINE                   │
│                                                             │
│  ┌───────────────────────┐      ┌────────────────────────┐  │
│  │   Telemetry Engine    │      │    Predictive Models   │  │
│  │  - Collector Loop     │      │  - Linear Bill Forecast│  │
│  │  - NNLS Attribution   │      │  - Carbon Equivalents  │  │
│  │  - Process Tree Match │      │  - Load Directives     │  │
│  └───────────▲───────────┘      └────────────────────────┘  │
└──────────────┼──────────────────────────────────────────────┘
               │  ctypes / subprocess / WMI / CIM
┌──────────────▼──────────────────────────────────────────────┐
│                    HARDWARE SENSOR LAYER                    │
│  Windows: RAPL EMI · CallNtPowerInformation · nvidia-smi    │
│  macOS:   ioreg Battery · IOReport GPU Energy               │
│  Linux:   sysfs powercap · RAPL DRAM/Core                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📡 API Endpoints Summary

| Endpoint | Method | Description |
|---|---|---|
| `/api/live` | `GET` | Instantaneous system watts, component breakdown, and active AI processes |
| `/api/system` | `GET` | Detected hardware specification (CPU, GPUs, RAM, battery, active sensors) |
| `/api/usage` | `GET` | Historical energy consumption (kWh) and costs per model |
| `/api/usage/log` | `GET` | Timestamped records (IDE, AI app, model, effort, watts) and energy totals by date, IDE, app, model and effort; `?format=csv` to export |
| `/api/forecast` | `GET` | End-of-cycle bill projection with baseline comparison |
| `/api/impact` | `GET` | Bill increase decomposition (AI share vs rate hikes) + Carbon Equivalents |
| `/api/recommendations` | `GET` | Algorithmic savings rules (STOP idle, SWITCH model, REDUCE footprint) |
| `/api/device/start` | `POST` | Activates real-time background hardware telemetry sampling |
| `/api/device/status` | `GET` | Current daemon health, sample count, and calibrated power model |

---

## 🚀 Setup & Execution Guide

### Prerequisites
* **Python 3.10+** (MSYS2 UCRT64, Windows Python, or standard Linux/macOS)
* **Node.js 18+** & npm

### Terminal 1: Python Backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# (or if using MSYS2: .\.venv\bin\Activate.ps1)
pip install -r requirements.txt
python run.py
```
*Server starts on `http://127.0.0.1:5001`*

### Terminal 2: React Frontend
```bash
cd frontend
npm install
npm run dev
```
*Frontend starts on `http://localhost:5173`*

---

## 🧪 Verification & Automated Tests
To run the automated test suite across all telemetry, sensor, and forecasting modules:
```bash
cd backend
python -m pytest tests
```
*(132 passed, 5 skipped platform-specific tests)*
