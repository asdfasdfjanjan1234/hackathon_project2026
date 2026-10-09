# Demo Script — Watt-Trace

3 minutes on stage, then Q&A. The arc: **hook → live measurement → verdict → fix → proof**.

> "Everyone blames AI for their electric bill. We built the tool that measures it, and tells you the truth. For most people it's the aircon. For people running AI on their own GPU it's real money, and we show which model, how to cut it, and when to run it."

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
   In `.env`, set `ELECTRICITYMAPS_TOKEN=` to a free personal token from app.electricitymaps.com, and `ELECTRICITYMAPS_ZONE=PH-LU` (PH-VI Visayas, PH-MI Mindanao). Without it the Cleanest Hours card stays empty.
   ```powershell
   ```
3. Pull a big and a small model of the same family that fit the GPU. On a 6–8 GB laptop GPU: `ollama pull llama3.1:8b` and `ollama pull llama3.2:3b`. (70B models don't fit a laptop GPU.)
4. **Run `python preflight.py`.** It reads every sensor, nvidia-smi, Ollama and the database with the app's own code and prints PASS / WARN / FAIL with the fix. Fix every FAIL. Also try it once from an **Administrator** PowerShell: if the EMI channels only show up there, run the backend as Administrator on stage.
5. `cd ..\frontend; npm install`

### Checklist

- [ ] `python preflight.py` shows **0 to fix**, including "runs on GPU", a "switch pair" and "Electricity Maps: token set".
- [ ] **Record some usage of the big model on the demo day,** so the dashboard has a "SWITCH" recommendation for it. With `demo_load.py`, 20–30 minutes is enough. Run some of it in the evening (peak hours), so the Best Time and Cleanest Hours cards have a shift to show.
- [ ] **Plug-in power meter.** Do at least 5 spot checks and one energy check of an hour or more (This Device → Wall-Meter Check). Quote the average difference it shows: **[fill in] %**.
- [ ] **Rehearse with a timer** at least three times. Write down the real watt jump: idle **[fill in] W** → big model **[fill in] W** → small model **[fill in] W**.
- [ ] **Tariff & Hardware** filled in from a real Meralco bill: rate, this month's bill, budget, billing cycle start day, carbon budget, and tariff (same rate all day, or Peak/Off-Peak with the bill's peak and off-peak rates).
- [ ] Write down the grid numbers on the day: cleanest window **[fill in]** at **[fill in] g CO₂/kWh**, and the CO₂ the shift avoids **[fill in] g/month** (Carbon Ledger → Cleanest Hours to Run AI).
- [ ] **Record a video** of a full run-through as a fallback.

## 30 minutes before

1. Laptop plugged in through the power meter, on the **Best performance** power mode, with the meter visible to the audience or on camera.
2. Terminal 1: `cd backend; .\.venv\Scripts\Activate.ps1; python preflight.py --no-load`, then `python run.py`. Terminal 2: `cd frontend; npm run dev`. Open http://localhost:5173.
3. Click **This Device → Start reading my device**, so the reader has run for more than 30 s before any spot check.
4. Terminal 3, ready but **not started**: `cd backend; .\.venv\Scripts\python demo_load.py --model llama3.1:8b`
5. Close other heavy apps (browsers with many tabs, Docker) so the jump is clean.
6. Check the tariff (Tariff & Hardware) matches the bill.
7. Open **Carbon Ledger** once and check **Cleanest Hours to Run AI** shows the hourly chart. The backend keeps the grid data for 15 minutes, so do this close to going on stage.

---

## The 3 minutes

| Time | Say | Do |
|---|---|---|
| 0:00 | "Your electric bill went up. Everyone's saying it's AI. Is it?" | Dashboard (**Telemetry Console**) on screen. |
| 0:12 | "Most tools guess. We measure. This app reads this laptop's power sensors, with no extra hardware, and finds every AI app running." | Click **This Device**. Point at the sensor list (measured vs. estimated) and **AI apps running now**. |
| 0:30 | "Claude Code and Copilot running right now: a fraction of a watt. For people using cloud AI, the honest answer is: AI didn't raise your bill." | Point at the AI apps' watts. |
| 0:42 | "But some people run AI on their own machine. Watch." | Start `demo_load.py` in terminal 3. |
| 0:50 | "There's the model. **[fill in] watts** and climbing, and the meter on the wall agrees." | Point at **Active Power Draw Monitor**, then the physical meter. |
| 1:02 | "Kept up 4 hours a day, that's **₱[fill in]** a month on this laptop. On a gaming PC it's ₱800 or more. For a 10-machine dev shop, multiply by ten." | **Telemetry Console** → **If You Kept This Up**. Set machines to 10. |
| 1:17 | "Say the bill went from ₱1,500 to ₱2,500. The app splits the increase: rate change, AI, everything else. Here AI explains **[fill in]%**." | **Billing Projection**. Show the verdict and the forecast lines. |
| 1:40 | "And it doesn't just tell you. It fixes it." | **Load Directives** → **Switch now** on the big model. |
| 1:50 | "Big model unloaded, small one loaded. The AI draw drops from **[fill in] W** to **[fill in] W**, right now." | Point at the "before → now" line on the card and the live dial. |
| 2:05 | "It also tells you *when* to run the heavy jobs. Luzon's grid is cleanest **[fill in]**, about **[fill in] g** of CO₂ per kWh. Moving the batch work there avoids **[fill in] g** a month, without changing the bill." | **Carbon Ledger** → **Cleanest Hours to Run AI**. Point at the green window and your AI hours under it. |
| 2:22 | "On Meralco's Peak/Off-Peak rate, those same night hours are also ₱2 cheaper per kWh." | **Telemetry Console** → **Best Time to Run Local AI**. Point at the third tile. |
| 2:35 | "Is any of this accurate? We checked against a power meter at the wall. Within **[fill in]%**, using only the laptop's own sensors." | **This Device → Wall-Meter Check**. Point at the average difference. |
| 2:50 | "Watt-Trace: the honest answer about AI and your bill, and the fix when it's real." | Done. |

**Don't show on stage** (keep for Q&A): cloud data-center Wh, Opus vs. Sonnet, per-host breakdown, Footprint by Model, the carbon budget, trees and EV equivalents, 12-month projections, reasoning effort, the per-component kWh table, the 7D / 30D / MTD switch.

If the 2:05 beat runs long, cut 2:22 (Best Time). It's the first thing to drop.

## If something breaks

| What breaks | Do this |
|---|---|
| Backend or frontend won't start | Play the recorded video. Keep talking over it. |
| Ollama is slow to load the big model | Start `demo_load.py` at 0:35 instead of 0:50, or preload the model beforehand with `ollama run llama3.1:8b ""`. |
| No **Switch now** button | The big model isn't loaded, or it has no recorded usage today. Use **Unload now** on any loaded model, or stop `demo_load.py` and show the watts falling. |
| The watts barely move | Say the number honestly ("on a laptop it's small"), then go straight to the 10-machine projection. |
| Spot check says "needs 30 s of readings" | The reader just started. Show the energy check done earlier instead. |
| Cleanest Hours says "Hourly grid data not connected" | The token is missing or wrong: preflight says which. On stage, skip 2:05 and go to Best Time (2:22), which works offline. |
| Cleanest Hours shows an error, or Wi-Fi is down | Only the hourly grid data needs the internet. Skip 2:05; everything else, including Best Time on the tariff, works offline. |
| "Already clean" / no shift on Cleanest Hours | Little AI use is recorded, or it already runs in clean hours. Say that honestly ("this machine already runs in the clean hours"), point at the chart, move on. |

## Judge Q&A

**"Isn't this all estimates?"**
The whole machine is measured: the battery controller on a Mac, RAPL or nvidia-smi on a PC. We checked it against a wall meter: **[fill in]%**. The split per app is calculated from each app's CPU and GPU share, fitted to that measured total, and we label it that way. Cloud AI energy is a clearly labeled estimate.

**"What about ChatGPT / Claude energy?"**
It runs in the provider's data center, so it isn't on your bill. We show an estimate from token counts per model (Opus vs. Sonnet), labeled as estimated, so people can still see the difference their model choice makes.

**"Where does the CO₂ number come from?"**
Totals use the DOE grid emission factor for the Philippines (0.7122 kg CO₂/kWh, set in `.env`). That's one number for the whole year, so for *which hour* is cleanest we use Electricity Maps' hourly carbon intensity for Luzon: the 24-hour forecast when available, otherwise the last 24 hours. If that data isn't connected, the card says so. We never make up hourly numbers.

**"If my rate is the same all day, why does timing matter?"**
On a flat rate it doesn't change the bill, only the CO₂, and the card says that. On Meralco's Peak/Off-Peak program, off-peak is about ₱2.14/kWh cheaper than the regular rate, so the same kWh costs less. On a flat rate, the Best Time card shows what Peak/Off-Peak would cost and whether the household qualifies (500 kWh a month average).

**"Who would pay for this?"**
Dev shops, schools and labs running local models on several machines, where the savings multiply (see the team view). Also anyone on high Philippine rates who's wondering whether to blame the aircon or the GPU.

**"Privacy?"**
Everything runs on the user's own computer. From app logs we read only model names and token counts, never prompts or code. The only outside call is the grid's hourly carbon intensity, which sends the grid zone and nothing about the user.

**"Does it work on Windows?"**
This demo is running on Windows: nvidia-smi for the GPU, the Energy Meter Interface for the CPU **[confirm with preflight]**, and Windows' per-process GPU counters to split the GPU between apps.

**"Why not just use a smart plug?"**
A smart plug shows the whole machine's power. It can't tell which app or model used it, or what to change. We use one only to prove our numbers.
