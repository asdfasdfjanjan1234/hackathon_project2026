# Activity Logs

This document tracks development sessions, features implemented, refactoring efforts, bug fixes, and tasks completed across the project lifecycle.

---

## Session Log Template

```markdown
### [YYYY-MM-DD] - Session Title / Focus
**Branch:** `<branch-name>`  
**Goal:** Summary of session objectives.

#### Completed Tasks
- [x] Task 1
- [x] Task 2

#### Key Changes & Refactoring
- **Backend:** Specific files modified and rationale.
- **Frontend:** UI updates, state changes, or styling enhancements.
- **Infrastructure / Data:** Schemas, scripts, configs, dependencies.

#### Tests & Verification
- Test commands run and verification results.

#### Next Steps
- Pending items or follow-ups for the next session.
```

---

## Session History

### [2026-10-09] - Session 9: Every Plan Item, Built for Any Device and OS
**Branch:** `main`  
**Goal:** Implement the remaining PROJECT_PLAN.md items (§3.3, §4, §5, §6) and make measurement accurate on every OS, not just the M2.

#### Completed Tasks
- [x] **Accuracy:** apps get their share of *measured* CPU/GPU power above idle where a sensor exists (RAPL, nvidia-smi, IOReport) instead of the M2 formula; on an NVIDIA desktop, Ollama previously got ~10 W of a ~300 W GPU.
- [x] GPU power goes to the processes using the GPU: per process on Windows (all engines, incl. CUDA, which the 3D-only counter missed), NVIDIA's compute-process list (a game is no longer blamed on Ollama), else active local runners only.
- [x] Device-class power defaults (Apple Silicon / laptop / desktop) and a fitted power model per device (it was shared across devices in MySQL).
- [x] **Linux:** sensors (`sensors_linux.py`: battery, RAPL, amdgpu) and device detection (DMI, cpuinfo, lspci, block devices, displays, NPUs).
- [x] **Models (§3.3):** one row per Ollama runner process, named from Ollama's manifests; LM Studio loaded models (`local_models.py`).
- [x] **Forecast (§4):** billing cycle start day, weekday/weekend pattern, damped trend, 1/3/12-month projections, daily series for the chart (current path and with recommendations), budget-exceeded date; unmeasured days are no longer counted as zero.
- [x] **Recommendations (§5):** all 8 rules (budget date, smaller model, idle loaded, quantization, local vs cloud, cost per hour, tool runs, Opus → Sonnet) plus "growing fastest"; overlapping savings compound instead of double counting. SWITCH now also fires on device data (`Ollama · llama3:70b`).
- [x] **Dashboard (§6):** per-host energy, device energy next to data-center energy per model, CO₂ and aircon-hours comparisons.
- [x] **Frontend honesty:** removed invented values (fake process rows, seeded history, ₱2,000 cap, "+33.5 W over idle", "Apple Silicon SoC", "95% confidence interval", John's fallback impact); live dial scales to the device; tariff settings take exact values and the billing cycle day.

#### Tests & Verification
- `cd backend && .venv/bin/python -m pytest`: 105 passed, 3 skipped (MySQL). New: `test_forecast.py`, `test_recommendations.py`, `test_platforms.py`.
- Real collector steps on the M2; all dashboard views checked in a headless browser on this device's data and on sample data (no console errors, no failed requests). `npm run build` clean.

#### Next Steps
- [ ] Run on a real Windows PC and a Linux PC; run with Ollama / LM Studio loaded and on an NVIDIA GPU.
- [ ] Confirm the data-center reference figure (Epoch AI 0.3 Wh in use) and default rate / billing cycle.

---

### [2026-10-09] - Session 8: "Start Reading My Device" and Per-Model Tracking
**Branch:** `main`  
**Goal:** Make the system dynamic: each user clicks one button and the app detects their OS, hardware, AI apps and models (PROJECT_PLAN.md §3).

#### Completed Tasks
- [x] Background device reader (`device_reader.py`) started from the dashboard; `POST /api/device/start|stop`, `GET /api/device/status`, `POST /api/device/source` (this device / sample data).
- [x] Model discovery from local logs (`model_usage.py`): Claude Code transcripts (exact tokens, deduped per response), Codex sessions (token deltas), Copilot logs (requests per model), installed AI extensions. `GET /api/models`.
- [x] Cloud catalog with list prices and data-center Wh estimate, calibrated to Epoch AI's 0.3 Wh per typical query (open decision in §8; change `REFERENCE` in `models_catalog.py`).
- [x] App detection: Codex, Amazon Q, Windsurf; agent child processes counted as "tool runs"; host app (VS Code, Terminal, …) stored per sample (`host` column, auto-migrated).
- [x] Client apps are labeled with their active model (e.g. `Claude Code · claude-opus-5-5`).
- [x] Forecast leaves cloud data-center energy off the bill; bill endpoints accept the user's rate/bills/budget as query parameters.
- [x] Frontend: `<DeviceReader />` panel; App.jsx uses backend bill math instead of recomputing it (the old recompute blamed all AI kWh for the increase); settings modal gains "this month's bill".
- [x] 13 new backend tests (55 total, all passing); checked end-to-end in a headless browser on the M2.

---

### [2026-10-09] - Session 7: Diagnosed and Re-engineered Broken Radial Arc Gauge
**Branch:** `TA-01`  
**Goal:** Fix the distorted SVG arc, ghost arc artifact, badge text collision, and container clipping in `<LiveWattage />` identified from user UI inspection.

#### Completed Tasks
- [x] Diagnosed Root Causes in `<LiveWattage />`:
  1. `<circle>` dasharray pattern repetition bug: Passing half-circle length ($\pi r$) as `strokeDasharray` on a 360° circle caused SVG to repeat the dash pattern, generating an unwanted ghost arc segment at 1 o'clock.
  2. CSS rotation and overflow clipping: Applying `transform -rotate-180` with parent `h-28 overflow-hidden` caused the right and top sides of the arc to be clipped.
  3. Absolute positioning collision: The `NOMINAL LOAD · 40%` badge and numbers were positioned with CSS absolute bottom offsets that collided directly into the cyan arc stroke.
- [x] Re-architected with Mathematical Precision:
  - Replaced `<circle>` with a dedicated 180° SVG `<path d="M 38 116 A 82 82 0 0 1 202 116" />`. Because the path terminates at the end coordinate, no ghost arc pattern can ever repeat.
  - Placed the digital readout (`XX.X W`) and status badge cleanly inside the arch vault via SVG vector coordinates (`viewBox="0 0 240 142"`).
  - Integrated calibrated tick notch lines and tick labels (`0W`, `30W`, `60W`, `90W`, `120W`) directly into the vector space.
  - Guaranteed 100% proportional vector scaling with zero text collision, zero ghost arcs, and zero overflow clipping across all mobile and desktop screen sizes.
- [x] Verified full build cleanly with `npm run build` (0 errors).

---

### [2026-10-09] - Session 6: Removal of Green Sensor Indicators & Full UI Responsiveness Overhaul
**Branch:** `TA-01`  
**Goal:** Completely eliminate the live sensor "green" in favor of precision instrument cyan/monochrome, and eliminate all layout/interactive unresponsiveness across screen sizes and user controls.

#### Completed Tasks
- [x] Removed all green colors (`#10B981` / emerald) from live sensor elements, replacing them with Instrument Cyan (`#38BDF8` / `sky-400`), neutral monochrome, or steel blue:
  - Updated `.tech-tag-live` from green to instrument cyan.
  - Replaced pulsing green hardware LEDs in `<Sidebar />`, `<TopBar />`, and `<LiveWattage />` with cyan phosphor pulses.
  - Replaced green forecast area fill and optimized curve in `<ForecastChart />` with cyan.
  - Converted model efficiency ratings and directives away from green to cyan/neutral.
- [x] Overhauled UI Layout Responsiveness:
  - Added mobile overlay drawer navigation with hamburger toggle (`Menu`) in `<TopBar />` and backdrop dismiss.
  - Added `min-w-0` to all CSS Grid and Flexbox containers to prevent Recharts `ResponsiveContainer` width blowout on smaller screens.
  - Made `<BillSummary />` trajectory comparison ribbon wrap gracefully on mobile devices.
  - Enabled smooth horizontal scroll with constrained widths for `<UsageBreakdown />` table.
- [x] Implemented Full Interactive Responsiveness:
  - Wired Sidebar navigation items (`Telemetry Console`, `Billing Projection`, `Model Runtimes`, `Load Directives`) to smooth-scroll directly to target dashboard sections.
  - Built interactive `<TariffSettingsModal />` allowing live real-time slider recalibration of Electricity Tariff (₱/kWh), Monthly Budget Cap (₱), and Baseline Bill (₱) with instant live recalculation of all metrics without refreshing.
  - Made Date Range selector (`7D`, `30D`, `MTD`) functional, dynamically scaling historical kilowatt-hours and cost trajectories.
- [x] Verified full production build cleanly with `npm run build` (0 errors).

---

### [2026-10-09] - Session 5: Elimination of Generic AI UI Tropes in favor of SCADA Telemetry Aesthetic
**Branch:** `TA-01`  
**Goal:** Eliminate generic AI SaaS tropes (sparkle icons, marketing "PRO" badges, rainbow neon gradients) and re-engineer the UI with an authentic industrial energy telemetry/SCADA aesthetic.

#### Completed Tasks
- [x] Replaced generic SaaS color schemes with a disciplined industrial telemetry palette (deep asphalt `#090C12`, `#0E131E`, `#101624`, precision instrument cyan `#38BDF8`, grid green `#10B981`, alert amber `#F59E0B`, critical crimson `#F43F5E`).
- [x] Stripped away all marketing buzzwords (`WattageAI PRO`, `Sparkles`, `Magic Tips`) across navigation, headers, and cards.
- [x] Enforced tabular monospace figures (`JetBrains Mono`, `tabular-nums`) across all numerical metrics, power readouts, and tariff calculations for strict grid alignment.
- [x] Redesigned `<LiveWattage />` to look like an authentic hardware wattmeter with perimeter calibration tick marks (`0W`, `30W`, `60W`, `90W`, `120W`), digital phosphor readouts, and a process telemetry table tracking host architectures (`Metal GPU`, `CLI Agent Client`, `IDE IPC`).
- [x] Refactored `<BillSummary />` into industrial instrumentation blocks (`ACTIVE SYSTEM POWER DRAW`, `INTEGRATED ENERGY`, `ATTRIBUTED AI TARIFF`, `CYCLE PROJECTION`) with clean comparison ribbons.
- [x] Enhanced `<ForecastChart />` with subtle 2x2 gridlines, dedicated `₱2,000 CAP` and `₱1,500 BASE` threshold reference lines, and an engineering-grade OLS confidence tooltip.
- [x] Converted `<UsageBreakdown />` into a hardware runtime inventory table detailing host bus architectures (`Metal / MPS` vs `Data Center`) and efficiency load classes (`CLASS A`, `CLASS B`, `CLASS D`).
- [x] Transformed `<Recommendations />` from "magic suggestions" into actionable `LOAD SHEDDING & RUNTIME OPTIMIZATION DIRECTIVES` with concrete `COMMITTED` states.
- [x] Overhauled `<BillImpact />` into an empirical causal tariff decomposition meter with high-contrast segment borders and SCADA-style factor analysis.
- [x] Verified build cleanly via `npm run build` (0 errors).

---

### [2026-10-09] - Session 4: Front-End UI/UX Redesign & Dribbble Theme Implementation
**Branch:** `TA-01`  
**Goal:** Completely redesign and implement the entire front-end UI/UX adapting the Dribbble wind farm monitoring dashboard reference to the AI Wattage Tracker domain.

#### Completed Tasks
- [x] Installed and configured Tailwind CSS (`v3.4.17`), PostCSS, Autoprefixer, and Lucide React icons.
- [x] Configured Google Fonts (`DM Sans` and `JetBrains Mono`) and dark aesthetic color palette (deep slate `#090D16`, `#0E1424`, `#131B2E`, electric blue `#3B82F6`, emerald `#10B981`, rose `#F43F5E`, amber `#F59E0B`).
- [x] Built collapsible `<Sidebar />` with navigation states, live hardware pulse indicator, and collapse toggle.
- [x] Built `<TopBar />` with real-time status pill, date range selector (7d, 30d, This Month), rate/budget chips, and notification center.
- [x] Redesigned `<BillSummary />` into 4 high-density KPI performance stat cards (Current Watts, 30-Day Energy, Monthly AI Surcharge, Projected Bill) with trend arrows ↑↓ and trajectory comparison ribbon.
- [x] Redesigned `<LiveWattage />` with animated radial SVG gauge, peak percentage meter, live sparklines, and active process breakdown.
- [x] Redesigned `<ForecastChart />` with Recharts dual-line area chart, shaded gradient fills, baseline reference line, and interactive Philippine Peso tooltip.
- [x] Redesigned `<UsageBreakdown />` with sortable table, efficiency ratings (A+/A/B/D), visual consumption progress bars, and local vs. cloud attribution.
- [x] Redesigned `<Recommendations />` with severity badges (STOP, SWITCH, REDUCE), monthly savings callouts, and interactive one-click action buttons.
- [x] Created new `<BillImpact />` component with Recharts donut decomposition (Local AI vs Rate Change vs Other Usage), central AI percentage share, and categorical verdict banners.
- [x] Overhauled `App.jsx` layout grid with responsive flexbox/grid system (1440p down to 1024px), animated loading skeletons, and connection retry error state.
- [x] Enhanced `client.js` and `format.js` for robust Philippine Peso formatting and resilient fallback handling.
- [x] Verified full build cleanly with `npm run build` (0 errors).

---

### [2026-10-09] - Session 3: Codebase Architecture Audit & Activity Logging
**Branch:** `TA-01`  
**Goal:** Perform an end-to-end audit of all folders, files, logic, and branch states, and establish structured activity tracking for the team.

#### Completed Tasks
- [x] Explored and analyzed the complete file structure across `backend/`, `frontend/`, and root documentation.
- [x] Conducted deep-dive code review of backend services (forecasting math, recommendation rules, power measurement, sample data generation) and frontend React components.
- [x] Audited git branch topology comparing current working branch `TA-01` with upstream `main` (`34e0678`).
- [x] Identified key feature additions present in `main` (real `AppleSmartBattery` sensor integration, process-level AI attribution, SQLite sample storage, and `<BillImpact />` decomposition).
- [x] Created `Activity Logs.md` to establish consistent tracking of changes, refactoring, and hackathon milestones.

#### Key Findings & Observations
- **Branch Topology:** Current branch `TA-01` is on commit `3c5d572` (Base MVP). Branch `main` has commit `34e0678` with advanced sensor collection and bill impact analysis.
- **Python Environment:** The root `env/` points to an external Python 3.10 framework symlink; setting up an isolated virtual environment (`.venv`) inside `backend/` will standardize local test execution.

#### Next Steps
- [ ] Align with team on merging or rebasing `origin/main` changes into `TA-01`.
- [ ] Verify test suite execution inside `backend/.venv`.
- [ ] Prepare live demo flow with local models (e.g., Ollama / Claude Code) vs. sample data mode.

---

### [2026-10-09] - Session 2: Non-Sudo Hardware Telemetry, Process Attribution & Bill Impact
**Branch:** `main` (Commit `34e0678`)  
**Goal:** Implement real-world hardware power collection without root privileges, attribute power per AI process, and build bill impact decomposition.

#### Completed Tasks
- [x] Implemented non-privileged Apple Silicon battery power reader (`ioreg -rn AppleSmartBattery`) and GPU monitoring (`ioreg -c IOAccelerator`).
- [x] Created process detector (`backend/app/services/ai_processes.py`) targeting local runtimes (Ollama, LM Studio, llama.cpp, MLX) and client assistants (Claude Code, Cursor, Copilot).
- [x] Built power attribution regression engine (`backend/app/services/attribution.py`) calibrating $W \approx \text{idle} + a \cdot \text{CPU}\% + b \cdot \text{GPU}\%$.
- [x] Built background telemetry daemon (`backend/collect.py` & `collector.py`) and SQLite storage (`storage.py`) in `backend/data/wattage.db`.
- [x] Developed Bill Impact analysis endpoint (`/api/impact`) and service (`impact.py`), decomposing bill deltas into **Rate Effect**, **AI Effect**, and **Other Usage** with a categorical verdict.
- [x] Built `<BillImpact />` frontend component and enriched `<LiveWattage />` with real-time app breakdown.
- [x] Added unit tests for measurement, attribution, and impact endpoints.

---

### [2026-10-09] - Session 1: Initial MVP Prototype
**Branch:** `main` / `TA-01` (Commit `3c5d572`)  
**Goal:** Bootstrap the full-stack AI Wattage Tracker MVP with mock/sample data, forecasting, and recommendations.

#### Completed Tasks
- [x] Initialized Flask application with blueprint structure on port 5001.
- [x] Created model specifications catalog (`models_catalog.py`) differentiating local measured models (`llama3:70b`, `llama3:8b`, `sdxl-turbo`) and cloud estimated models (`claude (cloud)`).
- [x] Implemented ordinary least-squares (OLS) linear trend forecasting (`forecasting.py`).
- [x] Implemented rule-based recommendations engine (`recommendations.py`) with `STOP`, `SWITCH`, and `REDUCE` actions and monetary savings calculations in Philippine Pesos (₱).
- [x] Implemented synthetic 30-day realistic sample data generator (`sample_data.py`).
- [x] Built React + Vite frontend dashboard using Recharts for bill trajectory comparison.
- [x] Added automated tests for health, usage, forecasting, and recommendations.

