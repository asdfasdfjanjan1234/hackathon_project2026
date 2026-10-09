# AI Wattage Tracker — Project Plan

Software that measures how much electricity AI models (coding agents, chatbots, image generators) use, forecasts the user's electricity bill, and recommends ways to reduce it.

**Example:** John's bill was ₱1,500 before he used AI. After he started using different AI models, it rose to ₱2,500. Our app shows how much each model contributed, what his next bills will be if he keeps going, and what he can change.

## Core question: did AI increase the bill?

The app doesn't assume AI caused a bill increase. It measures how much of the increase AI explains:

| Part of the increase | How it's calculated |
|---|---|
| Rate effect | baseline kWh × (current rate − baseline rate). Not caused by usage. |
| AI effect | measured local-model kWh × current rate (capped at the consumption increase) |
| Other usage | consumption increase that AI doesn't explain (aircon, appliances, etc.) |

Cloud AI energy is shown separately but never counted in the bill, because the provider's data center pays for it.

**Verdict** (AI share of the increase): ≥50% *major* · 20–50% *contributing* · under 20% *minor* · 0 *none*.

**With the current sample data:** John's bill went from ₱1,500 to ₱2,500. Local AI used 72 kWh (≈ ₱866), so AI explains about 87% of the increase. Verdict: *major*. These figures come from synthetic data and will change once real measurements are in.

**Ways to strengthen the evidence later:** an "AI-off week" vs. "AI-on week" experiment, or daily meter readings compared with daily AI kWh.

---

## 1. Where the electricity is actually used

| Type | Examples | On the user's bill? | How we get the number |
|---|---|---|---|
| **Local models** | Ollama, LM Studio, Stable Diffusion on own GPU | **Yes** | **Measured** (real watts) |
| **Cloud models** | Claude, ChatGPT, Gemini, Copilot, Cursor | **Almost none**: the model runs in the provider's data center | **Estimated** from token usage |

**Rough check (assuming ~₱12/kWh; adjust to the local rate):**
- A ₱1,000 increase ≈ 83 kWh/month ≈ a 300W GPU running local models ~9 hours/day.
- Heavy cloud use (~500 prompts/day) ≈ only a few kWh/month, billed to the data center, not to the user.

The app keeps **measured** and **estimated** values separate and labels them clearly.

---

## 2. Measurement (from device resources)

All values come from the device's own resource readings while AI apps run. `backend/collect.py` does the sampling.

| Reading | Source on Apple Silicon (no sudo) | How often |
|---|---|---|
| Total system watts (measured) | Battery controller via `ioreg -rn AppleSmartBattery` | Averaged about once a minute |
| CPU % (system) | `psutil` | Every 2 s |
| GPU % | `ioreg -c IOAccelerator` | Every 2 s |
| CPU % and memory per AI app | `psutil`, matched by process name/path | Every 2 s |
| Which Ollama model is loaded | Ollama API `/api/ps` | Every 2 s |

**Turning readings into watts per app:**
1. Each time the battery controller reports a new average, store it with the average CPU % and GPU % for that minute.
2. Fit `watts ≈ idle + a·CPU% + b·GPU%` with non-negative least squares. This calibrates the formula to this specific device. Until there are about 8 readings, rough M2 defaults are used.
3. Each AI app gets `a × its CPU share`, plus `b × GPU%` for local model runners. Idle power is never assigned to AI.
4. Energy = watts × seconds, summed per app per day → kWh.

**App types:** *local* (Ollama, LM Studio, llama.cpp, MLX): the model runs on the device, so inference energy is on the bill. *client* (Claude Code, Claude Desktop, ChatGPT, Cursor, Copilot, OpenCode): only the app's own device energy is on the bill; the model's energy is used in the provider's data center.

**First real reading (M2 MacBook Air, Oct 9, 2026):** whole laptop ~4.5 W; Claude Code + Copilot clients 0.01–0.18 W.

**Upgrades:** `sudo powermetrics` for CPU/GPU power split and per-process GPU time; `nvidia-smi` on PCs; desktop Macs have no battery sensor, so they rely on the default model or a smart plug.

---

## 3. Bill forecasting

**Simple version:**

```
forecast_bill = baseline_bill + Σ (projected_kWh per model × electricity rate)
projected_kWh = kWh used so far + average daily kWh × days left in billing cycle
```

**Better version:**
- Fit a trend line to daily usage per model, so growing usage gives a growing forecast.
- Account for weekday vs. weekend patterns.
- Show 1-month, 3-month and 12-month projections.

**Main visual: two lines on one chart**
- 🔴 "If you keep using it like this": ₱2,500 → ₱2,800 next month
- 🟢 "If you follow our recommendations": ₱1,900

---

## 4. Recommendations

Rule-based logic, driven by the measured data. Each recommendation is **Stop**, **Switch** or **Reduce**, and shows the expected savings.

| Trigger | Recommendation |
|---|---|
| Forecast goes over the user's monthly budget | "At this rate you'll exceed your ₱2,000 budget by Oct 24. Reduce use of `llama3:70b`." |
| A big model is used for small tasks | "`llama3:70b` uses ~4× the energy of `llama3:8b`. Switch for simple tasks and save ~₱400/month." |
| A model stays loaded while idle | "Ollama kept a model in GPU memory for 6 idle hours (~₱50 wasted). Unload it after use." |
| A smaller (quantized) version exists | "Use the Q4 version: about the same quality, less power." |
| Local use is heavy and cloud would be lighter on the bill | "Running this locally costs you ₱X/month; a cloud model would barely affect your bill." |
| Model has the worst energy per task | "Stop using `model X`. It costs ₱X per 1,000 tokens, the highest of your models." |

**Example output:**

```
⚠️  Forecast: ₱2,650 this month (+₱1,150 from AI)
    Top consumer: llama3:70b — 62 kWh/month (₱744)

💡 Recommendations
   1. SWITCH llama3:70b → llama3:8b for coding tasks      saves ₱520/mo
   2. UNLOAD idle models after 10 min                     saves ₱90/mo
   3. STOP using sdxl-turbo overnight batch jobs          saves ₱210/mo

   Projected bill with recommendations: ₱1,830
```

---

## 5. Architecture

```
Measure (watts per model) → Store (daily kWh per model)
   → Forecast (trend + billing cycle) → Recommend (rules) → Dashboard
```

**Dashboard shows:**
- Watts and kWh per model, per day and per month
- Cost in pesos, using the user's own electricity rate
- "Bill without AI vs. with AI"
- Bill forecast (current path vs. with recommendations)
- Recommendations with savings
- Optional: CO₂ equivalent and comparisons like "= X hours of running an aircon"

**Suggested stack:**
- Python backend: `psutil`, `powermetrics`/`nvidia-smi` parsing, FastAPI
- Web dashboard with live charts
- Small proxy or log reader for cloud token counts
- Sample-data generator, so the forecast and recommendations still work in the demo if live measurement isn't ready

---

## 6. Demo plan

1. Run a local model on stage and show the live wattage graph climb.
2. Show the per-model breakdown and the "without AI vs. with AI" bill.
3. Show the forecast chart: current path vs. following recommendations.
4. Show the recommendations and how much they save.

## 7. Open decisions

- [x] Hardware for the demo: Mac with Apple Silicon
- [x] Stack: Flask backend + React (Vite) frontend
- [ ] Which AI tools does the team actually use (for the cloud estimates)?
- [ ] Electricity rate and billing cycle to use as defaults
