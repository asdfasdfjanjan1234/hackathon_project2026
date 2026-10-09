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

| Time | Slide / Screen | Speaker Dialogue |
|---|---|---|
| **0:00 - 0:45** | **The Problem** | *"In 2026, everyone is running AI agents, local LLMs, and image generators. But developers have no idea how much power their workstation is consuming or whether AI is responsible for their ₱1,000 electric bill surge. Today, we built WATT-TRACE SCADA — the first hardware telemetry and FinOps engine for AI."* |
| **0:45 - 1:30** | **Telemetry Console** | *(Open `http://localhost:5173`)* <br>*"Here is our live SCADA console. On this machine, our backend connects directly to Windows RAPL counters and our NVIDIA RTX 3050 GPU. Notice the baseline draw is ~12W. Now we start a real local model [run `python demo_load.py --model llama3:70b`] and the live watts climb as Ollama works. The device reader attributes the draw to the model, and the forecast updates with it."* |
| **1:30 - 2:15** | **Billing & Carbon Matrix** | *(Click 'Billing Projection')* <br>*"We decompose the bill surge into Rate Hikes, Non-AI appliances, and Local AI Metal/CUDA draw. Furthermore, we translate raw kWh into real-world Green Computing metrics: exact kg of $\text{CO}_2$, trees needed for monthly offset, and EV driving distance."* |
| **2:15 - 3:00** | **Actionable Directives** | *(Click 'Load Directives')* <br>*"Unlike passive dashboards, we provide actionable load directives: unloading idle local models from VRAM saves ₱240/mo, and switching high-volume repetitive queries from Opus to Sonnet cuts data-center carbon by 60%."* |

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
