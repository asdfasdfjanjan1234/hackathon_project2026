# AI Wattage Tracker — Project Plan

Software that measures how much electricity AI models (coding agents, chatbots, image generators) use, forecasts the user's electricity bill, and recommends ways to reduce it.

**The pitch, in three parts** (based on what we measured; see section 1):

1. **"Did AI really raise your bill?"** The app gives an honest answer. For most people using cloud AI it's "no: AI explains almost none of the increase, look at the aircon instead", and that answer is still useful.
2. **Local AI is where the bill impact is real.** Models running on the user's own GPU are measured directly, shown in pesos, and come with fixes: smaller models, unloading idle ones.
3. **Cloud AI is about awareness.** Claude, ChatGPT and Copilot run in the provider's data center, so they barely touch the user's bill. The app shows their estimated data-center energy per model (Opus vs. Sonnet), clearly labeled as estimated.

**Two example users:**
- **John** runs local models (`llama3:70b`, Stable Diffusion) on a gaming PC with a large NVIDIA GPU, about 4 hours a day. His bill went from ₱1,500 to ₱2,500. The app shows local AI explains most of the increase, which models caused it, his next bills if he keeps going, and what to change.
- **Maria** vibe codes with Claude Code and Copilot on a MacBook, 8 hours a day. The app shows AI adds less than ₱1 a month to her bill. It also shows the estimated data-center energy of her Opus usage, and that switching simple tasks to Sonnet would roughly halve that estimate for those tasks.

## Core question: did AI increase the bill?

The app doesn't assume AI caused a bill increase. It measures how much of the increase AI explains:

| Part of the increase | How it's calculated |
|---|---|
| Rate effect | baseline kWh × (current rate − baseline rate). Not caused by usage. |
| AI effect | measured local-model kWh × current rate (capped at the consumption increase) |
| Other usage | consumption increase that AI doesn't explain (aircon, appliances, etc.) |

Cloud AI energy is shown separately but never counted in the bill, because the provider's data center pays for it.

**Verdict** (AI share of the increase): ≥50% *major* · 20–50% *contributing* · under 20% *minor* · 0 *none*.

**With the current sample data (John's gaming PC):** his bill went from ₱1,500 to ₱2,500. Local AI used 72 kWh (≈ ₱866), so AI explains about 87% of the increase. Verdict: *major*. These figures come from synthetic data. They match a ~600 W PC running local models 4 hours a day, but they aren't measured.

**Maria's case (measured on our M2):** AI apps used 0.01–0.18 W on her laptop, under ₱1 a month. Verdict: *none* or *minor*, whatever her bill did.

**Ways to strengthen the evidence later:** an "AI-off week" vs. "AI-on week" experiment, or daily meter readings compared with daily AI kWh.

---

## 1. Where the electricity is actually used

| Type | Examples | On the user's bill? | How we get the number |
|---|---|---|---|
| **Local models** | Ollama, LM Studio, Stable Diffusion on own GPU | **Yes** | **Measured** (real watts) |
| **Cloud models** | Claude, ChatGPT, Gemini, Copilot, Cursor | **Almost none**: the model runs in the provider's data center | **Estimated** from token usage |

**What the numbers show (at ₱12/kWh; adjust to the local rate):**

| Scenario | Power | Use | kWh / month | Cost / month | Source |
|---|---|---|---|---|---|
| MacBook Air M2 while vibe coding | ~7 W | 8 h/day | ~1.7 | ~₱20 | Measured |
| Claude Code + Copilot on that laptop | 0.01–0.18 W | 8 h/day | under 0.05 | under ₱1 | Measured |
| Local model on the M2 | ~20 W | 4 h/day | ~2.4 | ~₱30 | Estimate; measure in rehearsal |
| Gaming PC running local models on a large GPU | ~600 W | 4 h/day | ~72 | ~₱860 | Estimate |

So a ₱1,000 increase from AI takes about 83 kWh a month, and only heavy local-model use on a powerful GPU gets there. Cloud AI barely moves the user's bill; its energy is used in the data center, which we can only estimate (section 3.3). AI apps also use memory (Claude Code holds ~300 MB per session), but memory use barely changes power: RAM draws about the same whether it's 30% or 90% full.

The app keeps **measured** and **estimated** values separate and labels them clearly.

---

## 2. Measurement (from device resources)

All values come from the device's own resource readings while AI apps run. `backend/collect.py` does the sampling, every 2 s.

### 2.1 Detecting the OS and devices

Before taking any reading, the collector works out which OS it's on and what hardware the computer has (`backend/app/services/system_info.py`). This runs once at startup and takes about 0.2 s on our M2. Python libraries handle the parts that work on every OS. Each OS's own hardware report fills in the rest, read once with `subprocess` and parsed as JSON. No extra packages are needed.

| What | Python library (any OS) | macOS: `system_profiler -json` | Windows: PowerShell CIM queries | Linux: sysfs, `/proc` |
|---|---|---|---|---|
| OS, version, architecture | `platform` | | | |
| Device type and model | `psutil` (has a battery → laptop) | Model name, e.g. "MacBook Air (Mac14,2)" | `Win32_ComputerSystem` (form factor, maker, model) | DMI vendor, product, chassis type |
| CPU | `psutil` (cores, max clock) | Chip, e.g. "Apple M2" | `Win32_Processor` (full name) | `/proc/cpuinfo` model name |
| RAM | `psutil` (total GB) | | | |
| GPUs | `shutil` + `nvidia-smi` (NVIDIA, any OS) | Name, cores, built-in or discrete | `Win32_VideoController` (name, integrated or discrete) | `lspci -mm`, else PCI vendor IDs |
| NPU (AI accelerator) | | Apple Neural Engine on Apple Silicon | `Win32_PnPEntity`, "ComputeAccelerator" class (e.g. Intel AI Boost, AMD Ryzen AI) | `/sys/class/accel` (intel_vpu, amdxdna) |
| Disks | | NVMe SSDs, size | `Get-PhysicalDisk` (NVMe / SATA SSD / HDD, size, USB) | `/sys/block` (NVMe / SSD / HDD, size, removable) |
| Displays | | Built-in or external, resolution | `WmiMonitorConnectionParams` (built-in or external) | DRM connectors (eDP = built-in) |
| Battery | `psutil` (percent, plugged in) | Health: max capacity, cycles | | Health from `power_supply` |

**What the results are used for:**
- **Choosing sensors:** OS and Apple Silicon pick the macOS or Windows readers below; an NVIDIA GPU adds `nvidia-smi`; a desktop has no battery, so there's no whole-machine reading.
- **Sizing estimates:** RAM size drives the memory estimate. Disk type drives the disk estimate: an NVMe SSD idles at about 0.05 W, a desktop hard drive at about 4 W.
- **Context in the app:** an NPU or discrete GPU tells us which local AI hardware is available. Displays are the biggest part of "other" on laptops.

The collector prints the detected devices at startup, and `GET /api/system` returns them:

```text
Detected macos 27.0.1 (arm64) on a laptop: MacBook Air (Mac14,2)
  CPU       Apple M2, 8 cores, 16.0 GB RAM
  GPU       Apple M2 (integrated)
  NPU       Apple Neural Engine
  Disks     APPLE SSD AP0256Z (nvme, 251 GB)
  Displays  Color LCD (built-in)
  Battery   66%, on battery
```

Mac detection is tested on our M2. The Windows and Linux parsers are tested against sample output but **still need a run on a real Windows PC and Linux PC**. If PowerShell fails, the basics from `platform` and `psutil` still come through.

### 2.2 Watts per part of the computer

Using what 2.1 detected, the collector picks that OS's sensors once (`measurement.py`). Each part is *measured* where the OS exposes a sensor, otherwise *estimated*, and every value is labeled with its source. `GET /api/system` shows which sensor each part uses.

| Part | macOS (Apple Silicon) | Windows | Linux | Fallback (estimated) |
|---|---|---|---|---|
| Whole machine | Battery controller, `ioreg -rn AppleSmartBattery` | Battery discharge rate, `CallNtPowerInformation` (on battery only) | Battery `power_now` (on battery only) | None: desktops and plugged-in PCs need a smart plug |
| CPU | `powermetrics`, only with passwordless sudo | Energy Meter Interface (EMI): RAPL cores or package, Intel and AMD | RAPL powercap (usually root only) | Fitted formula: `a · CPU%` |
| GPU | IOReport `GPU Energy` channel, **no sudo** | EMI RAPL PP1 (Intel integrated GPU) | RAPL uncore; amdgpu hwmon | Fitted formula: `b · GPU%` |
| | `nvidia-smi` for NVIDIA GPUs on any OS: watts, utilization and which processes run GPU compute | | | |
| RAM | Not available without root | EMI RAPL DRAM (mostly server CPUs) | RAPL DRAM | RAM GB × (0.03 W idle + 0.15 W × load) |
| Disk | Not available | Not available | Not available | By detected disk type × busy time: NVMe 0.05–3 W, SATA SSD 0.05–2 W, HDD 4–6 W |
| Other (display, Wi-Fi, …) | Whole machine − the four parts | Same | Same | |

Tested on our M2 (macOS 27, Oct 9, 2026): GPU measured 0.01–0.33 W. The IOReport CPU and DRAM channels exist but don't update without root, so CPU and RAM are estimated there. The Windows readers follow Microsoft's EMI documentation and the same approach Chromium and Firefox use, but **still need a test on a Windows PC**. If EMI is missing or access is denied, they fall back to estimates.

### 2.3 Other readings and watts per app


| Reading | macOS | Windows |
|---|---|---|
| CPU % (system) | `psutil` | `psutil` |
| GPU % | `ioreg -c IOAccelerator` | Performance counter `\GPU Engine(*engtype_3D)\Utilization Percentage` |
| CPU % and memory per AI app | `psutil`, matched by process name/path | Same |
| Which Ollama model is loaded | Ollama API `/api/ps` | Same |

**Turning readings into watts per app:**
1. Each time the battery reports a new average, store it with the average CPU % and GPU % for that window. On Mac, the battery controller keeps running totals that update about once a minute. On Windows, the instant readings are averaged over 60 s.
2. Fit `watts ≈ idle + a·CPU% + b·GPU%` with non-negative least squares. This calibrates the formula to this specific device. Until there are about 8 readings, rough M2 defaults are used.
3. Each AI app gets `a × its CPU share`, plus `b × GPU%` for local model runners. Where the OS measures CPU or GPU power (RAPL, `nvidia-smi`, IOReport), apps get their share of the **measured power above idle** instead. GPU power goes to the processes using the GPU: per process on Windows, NVIDIA's list of compute processes, otherwise active local runners. Idle power is never assigned to AI.
   Until the formula is fitted, the defaults depend on the device: Apple M2, Windows/Linux laptop, or desktop (much higher idle and GPU power).
4. Energy = watts × seconds, summed per app per day → kWh.

**App types:** *local* (Ollama, LM Studio, llama.cpp, MLX): the model runs on the device, so inference energy is on the bill. *client* (Claude Code, Claude Desktop, ChatGPT, Cursor, Copilot, OpenCode): only the app's own device energy is on the bill; the model's energy is used in the provider's data center.

**First real reading (M2 MacBook Air, Oct 9, 2026):** whole laptop ~4.5 W; Claude Code + Copilot clients 0.01–0.18 W.

**Upgrades:** passwordless `sudo powermetrics` for measured CPU watts on Mac; desktops have no battery sensor, so they rely on measured CPU/GPU sensors, device defaults or a smart plug. (Done: per-process GPU % on Windows, across all GPU engines including CUDA.)

---

## 3. Which AI apps, and which models

Section 2 measures energy per **app**. This section goes one level deeper: which AI tools are installed or running (including inside VS Code), and which **model** each one is using (Opus 5.5, Sonnet 5.5, `gpt-5.3-codex`, `llama3:8b`, …).

### 3.1 Finding AI apps, including VS Code extensions

VS Code runs most extensions inside one shared process (`Code Helper (Plugin)`, the extension host). An extension can only be measured on its own if it starts its own program. Checked on our M2 on Oct 9, 2026:

| AI tool | Runs as | Measurable on its own? | Detection rule |
|---|---|---|---|
| Claude Code (CLI and VS Code extension) | its own `claude` binary | Yes | name `claude` (already in `ai_processes.py`) |
| GitHub Copilot (built into VS Code) | `copilot-runtime` inside `Visual Studio Code.app` | Yes | `copilot` in path (already) |
| OpenAI Codex extension | its own `codex` binary in `~/.vscode/extensions/openai.chatgpt-*/bin/` | Yes | **new:** name `codex` |
| Amazon Q | a language server under `~/Library/Caches/aws/language-servers/` | Probably; confirm while it's running | **new:** path match |
| Extensions that run inside the extension host (e.g. `kodu-ai.claude-dev`) | the shared extension host | No | **new:** list from `~/.vscode/extensions`; show as "installed, can't be measured separately" |
| Cursor, Windsurf | their own app (VS Code forks) | Yes, as a whole app | `/cursor.app/` (already); **new:** Windsurf |

Two more detection rules:
- **Child processes count toward the agent.** When Claude Code or Codex runs `npm test`, `pytest` or a build, that work uses the laptop's CPU and *is* on the bill. Today those processes aren't matched to any app. Add each AI app's child processes (`psutil.Process.children(recursive=True)`) to that app as "tool runs". These can use far more power than the agent's own process (0.01–0.18 W in our first reading).
- **Host.** Walk up the parent processes to record what started the app (VS Code, Terminal, iTerm), so the dashboard can show "Claude Code in VS Code" vs. "Claude Code in Terminal".

### 3.2 Finding which model each app uses

| App | Where the model name comes from | Token counts? |
|---|---|---|
| Claude Code | `~/.claude/projects/*/*.jsonl`: every response has `message.model` and `message.usage` | **Yes, exact:** input, output, cache read, cache write |
| Copilot Chat, Codex (in VS Code) | VS Code logs: `~/Library/Application Support/Code/logs/*/window*/exthost/{GitHub.copilot-chat,openai.chatgpt}/*.log` | No, model name only |
| Ollama | `/api/ps` (already); `eval_count` in each response | Yes |
| LM Studio | `lms ps` lists loaded models | To check |
| Claude Desktop, ChatGPT app, Cursor | nothing readable stored locally | No; shown as "unknown model" |

Only `model`, `usage` and timestamps are read from these files, never prompts or code.

**Real data from our M2 (all Claude Code sessions so far):**

| Model | Responses | Output tokens | Cache-read tokens |
|---|---|---|---|
| `claude-opus-5-5` | 405 | 690,345 | 30.7 M |
| `claude-opus-5` | 367 | 387,439 | 22.1 M |
| `claude-sonnet-5-5` | 7 | 18,779 | 0.3 M |

The VS Code logs on the same laptop also name `gpt-5.3-codex` (Codex) and `gpt-4o-mini` (Copilot).

### 3.3 Watts per model

The device readings (CPU %, GPU %, memory, and total system watts from section 2) work differently for local and cloud models.

**Local models (Ollama, LM Studio, MLX):** the model runs on the laptop, so the readings measure it directly.
- CPU and GPU: the runner's share of the fitted power formula (section 2), split between the loaded models.
- Memory: a loaded model holds gigabytes of RAM, but RAM adds little power on its own, and Apple Silicon doesn't report it separately without `sudo powermetrics`. Memory size is used to tell which model is loaded and to flag idle models that are still loaded.
- Each Ollama model runs in its own `ollama runner --model <blob>` process; the blob is matched to the model name through Ollama's manifests, so the model that's generating gets the power. Older Ollama versions (models inside the server) give it to the most recently used model. LM Studio's loaded models come from its REST API or `lms ps`.

**Cloud models (Opus, Sonnet, Haiku, GPT):** the model runs in the provider's data center. The laptop's CPU, GPU and memory look almost the same whether Claude Code is using Opus or Sonnet, so **device readings can't show the difference between cloud models.** Each cloud model gets two separate numbers:

| Number | What it covers | On the bill? | How we get it |
|---|---|---|---|
| Device energy | the app and its tool runs on this laptop while using that model | Yes | **Measured** (section 2). Each 2-second sample goes to the model of the app's most recent response, using the transcript timestamps. |
| Data-center energy | the provider's servers running the model | No | **Estimated:** tokens × energy per token for that model |

**Estimating data-center energy per model.** Providers don't publish energy per model, so we combine two inputs:
1. **A reference figure** from published estimates, for example: Google, median Gemini text prompt ≈ 0.24 Wh (Aug 2025); OpenAI, average ChatGPT query ≈ 0.34 Wh (June 2025); Epoch AI, ≈ 0.3 Wh per GPT-4o query (Feb 2025). Pick one, cite it, and show it in the app.
2. **How models compare**, using list price per token as a stand-in for compute. Price is the only public number that exists for every model and every token type, and it already charges much more for output tokens than for cache reads.

Current Claude list prices (USD per 1M tokens, as of Sep 25, 2026):

| Model | Input | Output | Data-center energy per output token, relative to Sonnet 5.5 |
|---|---|---|---|
| Fable 5.1 | $10 | $50 | 5× |
| Opus 5 | $5 | $25 | 2.5× |
| Opus 5.5 | $4 | $20 | 2× |
| Sonnet 5.5 | $2 | $10 | 1× |
| Haiku 4.5 | $1 | $5 | 0.5× |

```
list_cost      = Σ tokens of each type × that type's price   (input, output, cache read, cache write)
datacenter_Wh  = list_cost × k
k              = Wh per dollar, set once so that a typical query on the reference model = the reference figure
```

**Limitations, shown in the app:** price includes the provider's margin and business choices (Opus 5.5 costs less than Opus 5, so it's estimated lower). These numbers rank models; they don't measure them. They're always labeled *estimated*.

### 3.4 Code changes

| File | Change |
|---|---|
| `backend/app/services/ai_processes.py` | Add Codex, Amazon Q and Windsurf rules; add child processes to their parent app; record the host |
| new `backend/app/services/model_usage.py` | Read Claude Code transcripts and VS Code logs → tokens per model per day |
| `backend/app/services/models_catalog.py` | Replace `"claude (cloud)"` with one entry per model: provider, prices, relative energy |
| `backend/app/services/collector.py`, `storage.py` | Store the active model with each client-app sample; new `model_usage` table |
| `backend/app/routes/usage.py` | Add breakdowns by model and by host |

---

## 4. Bill forecasting

**Simple version:**

```
forecast_bill = baseline_bill + Σ (projected_kWh per model × electricity rate)
projected_kWh = kWh used so far + average daily kWh × days left in billing cycle
```

**Better version (built, `forecasting.py`):**
- Fit a trend line to daily usage per model, so growing usage gives a growing forecast. The trend levels off over time (damped), so a 12-month projection doesn't grow without limit.
- Account for weekday vs. weekend patterns (with a week or more of data).
- Show 1-month, 3-month and 12-month projections.
- Follow the user's billing cycle (meter read day), and leave out days the device reader didn't run instead of counting them as zero.

**Main visual: two lines on one chart**
- 🔴 "If you keep using it like this": ₱2,500 → ₱2,800 next month
- 🟢 "If you follow our recommendations": ₱1,900

---

## 5. Recommendations

Rule-based logic, driven by the measured data. Each recommendation is **Stop**, **Switch** or **Reduce**, and shows the expected savings.

| Trigger | Recommendation |
|---|---|
| Forecast goes over the user's monthly budget | "At this rate you'll exceed your ₱2,000 budget by Oct 24. Reduce use of `llama3:70b`." |
| A big model is used for small tasks | "`llama3:70b` uses ~4× the energy of `llama3:8b`. Switch for simple tasks and save ~₱400/month." |
| A model stays loaded while idle | "Ollama kept a model in GPU memory for 6 idle hours (~₱50 wasted). Unload it after use." |
| A smaller (quantized) version exists | "Use the Q4 version: about the same quality, less power." |
| Local use is heavy and cloud would be lighter on the bill | "Running this locally costs you ₱X/month; a cloud model would barely affect your bill." |
| Model has the worst energy per task | "Stop using `model X`. It costs ₱X per 1,000 tokens, the highest of your models." |
| An agent's tool runs (tests, builds) use a lot of power | "Claude Code's test runs used 1.2 kWh this week (₱14). Run only the affected tests." |
| A large cloud model is used for most work | "90% of your Claude Code tokens went to Opus 5.5, estimated at 2× Sonnet 5.5's data-center energy. Not on your bill, but ~X Wh less if you switch for simple tasks." |

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

## 6. Architecture

```
Measure (watts per model) → Store (daily kWh per model)
   → Forecast (trend + billing cycle) → Recommend (rules) → Dashboard
```

**Dashboard shows:**
- Watts and kWh per app, per model and per host (VS Code, Terminal), per day and per month
- For cloud models: device energy (measured, on the bill) next to data-center energy (estimated, not on the bill)
- Cost in pesos, using the user's own electricity rate
- "Bill without AI vs. with AI"
- Bill forecast (current path vs. with recommendations)
- Recommendations with savings
- CO₂ equivalent and comparisons like "= X hours of running an aircon" (Philippine DOE grid factor, 1 HP aircon; configurable)

**Suggested stack:**
- Python backend: `psutil`, `powermetrics`/`nvidia-smi` parsing, FastAPI
- Web dashboard with live charts
- Log reader for cloud token counts (Claude Code transcripts, VS Code logs); no proxy needed
- Sample-data generator, so the forecast and recommendations still work in the demo if live measurement isn't ready

---

## 7. Demo plan

1. **Maria (live, on the Mac):** start `collect.py`, show the detected devices and the AI apps. Claude Code in VS Code adds a fraction of a watt: AI didn't raise her bill. Show its per-model breakdown (Opus 5.5 vs. Sonnet 5.5) with the estimated data-center energy.
2. **Local AI (live, on the Mac):** run Ollama and show the live wattage climb. We expect about 5 W → 20 W; measure it in rehearsal. Small in pesos, but clearly visible.
3. **John (sample data, labeled as such):** the gaming-PC case. Show the "without AI vs. with AI" bill, the forecast (current path vs. following recommendations) and the recommendations with savings. If a teammate has a Windows PC with an NVIDIA GPU, run this one live instead.

## 8. Open decisions and risks

- [x] Hardware for the demo: Mac with Apple Silicon (plus a Windows PC with an NVIDIA GPU, if a teammate has one)
- [x] Stack: Flask backend + React (Vite) frontend
- [x] Which AI tools the team uses: detected automatically (section 3)
- [ ] Reference figure for cloud data-center energy (Google 0.24 Wh, OpenAI 0.34 Wh or Epoch AI 0.3 Wh per query). The code uses Epoch AI's 0.3 Wh for now.
- [ ] Electricity rate and billing cycle to use as defaults
- [ ] Test the Windows sensors and device detection on a real Windows PC (the code is only tested against sample data)
- [ ] Test the Linux sensors and device detection on a real Linux PC, and Ollama / LM Studio / NVIDIA with them running (tested against sample output only)
- [ ] Rehearse the Ollama demo on the Mac and record the real watt jump for step 2

**Risks and how we handle them:**

| Risk | How we handle it |
|---|---|
| Judges question "AI added ₱1,000 to the bill" | Only claim it for local models on a big GPU (John). For cloud AI, say plainly that it's under ₱1 (Maria). |
| Cloud data-center energy is a rough estimate | Always labeled *estimated*, with the reference figure cited (section 3.3) |
| Per-app watts are estimated from CPU/GPU share | The whole-laptop and GPU readings are measured; per-app splits are labeled as calculated |
| Windows code untested | Every Windows sensor falls back to estimates if it fails; test before demo day |
| John's numbers are synthetic | Label them "sample data" on screen, or replace them with a live run on a gaming PC |
