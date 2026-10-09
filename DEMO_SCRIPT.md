# Demo Script — AI Wattage Tracker

3 minutes on stage, then Q&A. The arc: **hook → live measurement → verdict → fix → proof**.

> "Everyone blames AI for their electric bill. We built the tool that measures it, and tells you the truth. For most people it's the aircon. For people running AI on their own GPU it's real money, and we show which model and how to cut it."

Numbers marked **[fill in]** come from rehearsal. Never say a number on stage that we didn't measure.

---

## Before demo day

The demo runs on the **Windows laptop with the NVIDIA GPU**, plugged in. Gaming laptops cut GPU power on battery, so stay on AC: GPU (nvidia-smi) and CPU (Energy Meter Interface, if the laptop has it) are still measured, but Windows only reports whole-machine watts on battery. The wall meter covers the whole machine.

### Windows laptop setup (PowerShell)

1. Install **Python 3.10+** (python.org, tick "Add to PATH"), **Node.js 18+**, **Git**, and **Ollama** (ollama.com). Update the NVIDIA driver; `nvidia-smi` should print the GPU.
2. Clone the repo, then:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   pip install -r requirements.txt
   copy .env.example .env             # leave DATABASE_URL unset: SQLite needs no setup
   ```
3. Pull a big and a small model of the same family that fit the GPU. On a 6–8 GB laptop GPU: `ollama pull llama3.1:8b` and `ollama pull llama3.2:3b`. (70B models don't fit a laptop GPU.)
4. **Run `python preflight.py`.** It reads every sensor, nvidia-smi, Ollama and the database with the app's own code and prints PASS / WARN / FAIL with the fix. Fix every FAIL. Also try it once from an **Administrator** PowerShell: if the EMI channels only show up there, run the backend as Administrator on stage.
5. `cd ..\frontend; npm install`

### Checklist

- [ ] `python preflight.py` shows **0 to fix**, including "runs on GPU" and a "switch pair".
- [ ] **Record some usage of the big model on the demo day,** so the dashboard has a "SWITCH" recommendation for it. With `demo_load.py`, 20–30 minutes is enough.
- [ ] **Plug-in power meter.** Do at least 5 spot checks and one energy check of an hour or more (This Device → Wall-Meter Check). Quote the average difference it shows: **[fill in] %**.
- [ ] **Rehearse with a timer** at least three times. Write down the real watt jump: idle **[fill in] W** → big model **[fill in] W** → small model **[fill in] W**.
- [ ] **Record a video** of a full run-through as a fallback.

## 30 minutes before

1. Laptop plugged in through the power meter, on the **Best performance** power mode, with the meter visible to the audience or on camera.
2. Terminal 1: `cd backend; .\.venv\Scripts\Activate.ps1; python preflight.py --no-load`, then `python run.py`. Terminal 2: `cd frontend; npm run dev`. Open http://localhost:5173.
3. Click **This Device → Start reading my device**, so the reader has run for more than 30 s before any spot check.
4. Terminal 3, ready but **not started**: `cd backend; .\.venv\Scripts\python demo_load.py --model llama3.1:8b`
5. Close other heavy apps (browsers with many tabs, Docker) so the jump is clean.
6. Set the tariff (Tariff & Hardware) to the local rate.

---

## The 3 minutes

| Time | Say | Do |
|---|---|---|
| 0:00 | "Your electric bill went up. Everyone's saying it's AI. Is it?" | Dashboard (**Telemetry Console**) on screen. |
| 0:15 | "Most tools guess. We measure. This app reads this laptop's power sensors, with no extra hardware, and finds every AI app running." | Click **This Device**. Point at the sensor list (measured vs. estimated) and the AI apps panel. |
| 0:35 | "Claude Code and Copilot running right now: a fraction of a watt. For people using cloud AI, the honest answer is: AI didn't raise your bill." | Point at the AI apps' watts. |
| 0:50 | "But some people run AI on their own machine. Watch." | Start `demo_load.py` in terminal 3. |
| 1:00 | "There's the model. **[fill in] watts** and climbing, and the meter on the wall agrees." | Point at the live dial, then the physical meter. |
| 1:15 | "Kept up 4 hours a day, that's **₱[fill in]** a month on this laptop. On a gaming PC it's ₱800 or more. For a 10-machine dev shop, multiply by ten." | Dashboard → **If You Kept This Up**. Set machines to 10. |
| 1:35 | "Say the bill went from ₱1,500 to ₱2,500. The app splits the increase: rate change, AI, everything else. Here AI explains **[fill in]%**." | **Billing Projection**. Show the verdict and the two forecast lines. |
| 2:05 | "And it doesn't just tell you. It fixes it." | **Load Directives** → **Switch now** on the big model. |
| 2:15 | "Big model unloaded, small one loaded. The AI draw drops from **[fill in] W** to **[fill in] W**, right now." | Point at the "before → now" line on the card and the live dial. |
| 2:35 | "Is any of this accurate? We checked against a power meter at the wall. Within **[fill in]%**, using only the laptop's own sensors." | **This Device → Wall-Meter Check**. Point at the average difference. |
| 2:50 | "AI Wattage Tracker: the honest answer about AI and your bill, and the fix when it's real." | Done. |

**Don't show on stage** (keep for Q&A): cloud data-center Wh, Opus vs. Sonnet, per-host breakdown, CO₂, 12-month projections, reasoning effort, the per-component kWh table.

## If something breaks

| What breaks | Do this |
|---|---|
| Backend or frontend won't start | Play the recorded video. Keep talking over it. |
| Ollama is slow to load the big model | Start `demo_load.py` at 0:35 instead of 0:50, or preload the model beforehand with `ollama run llama3.1:8b ""`. |
| No **Switch now** button | The big model isn't loaded, or it has no recorded usage today. Use **Unload now** on any loaded model, or stop `demo_load.py` and show the watts falling. |
| The watts barely move | Say the number honestly ("on a laptop it's small"), then go straight to the 10-machine projection. |
| Spot check says "needs 30 s of readings" | The reader just started. Show the energy check done earlier instead. |
| Wi-Fi is down | Nothing here needs the internet. |

## Judge Q&A

**"Isn't this all estimates?"**
The whole machine is measured: the battery controller on a Mac, RAPL or nvidia-smi on a PC. We checked it against a wall meter: **[fill in]%**. The split per app is calculated from each app's CPU and GPU share, fitted to that measured total, and we label it that way. Cloud AI energy is a clearly labeled estimate.

**"What about ChatGPT / Claude energy?"**
It runs in the provider's data center, so it isn't on your bill. We show an estimate from token counts per model (Opus vs. Sonnet), labeled as estimated, so people can still see the difference their model choice makes.

**"Who would pay for this?"**
Dev shops, schools and labs running local models on several machines, where the savings multiply (see the team view). Also anyone on high Philippine rates who's wondering whether to blame the aircon or the GPU.

**"Privacy?"**
Everything runs on the user's own computer. From app logs we read only model names and token counts, never prompts or code.

**"Does it work on Windows?"**
This demo is running on Windows: nvidia-smi for the GPU, the Energy Meter Interface for the CPU **[confirm with preflight]**, and Windows' per-process GPU counters to split the GPU between apps.

**"Why not just use a smart plug?"**
A smart plug shows the whole machine's power. It can't tell which app or model used it, or what to change. We use one only to prove our numbers.
