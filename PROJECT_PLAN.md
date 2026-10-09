# AI Wattage Tracker — Project Plan

Software that measures how much electricity AI models (coding agents, chatbots, image generators) use, forecasts the user's electricity bill, and recommends ways to reduce it.

**Example:** John's bill was ₱1,500 before he used AI. After he started using different AI models, it rose to ₱2,500. Our app shows how much each model contributed, what his next bills will be if he keeps going, and what he can change.

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

## 2. Measurement

### Local models: real watts
- **Mac (Apple Silicon):** `sudo powermetrics` gives live CPU/GPU/Neural Engine power.
- **NVIDIA GPU:** `nvidia-smi --query-gpu=power.draw --format=csv`
- **Intel/AMD on Linux:** RAPL counters in `/sys/class/powercap`
- **Per-model attribution:** record idle power first, then record power while each model runs. The difference is that model's usage.

### Cloud models: estimates
- Count tokens from API responses, a local proxy, or tool logs (for example, Claude Code stores token usage in `~/.claude/projects/*.jsonl`).
- Multiply by a published energy-per-token or energy-per-prompt estimate for each model (for example, Google's ~0.24 Wh per median Gemini text prompt, or Hugging Face AI Energy Score benchmarks). Published estimates vary a lot, so these values are labeled as estimates.

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
