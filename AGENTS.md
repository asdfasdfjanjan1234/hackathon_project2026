# AGENTS.md

## Run
- Backend: `cd backend && source .venv/bin/activate && python run.py` (Flask on 127.0.0.1:5001)
- Frontend: `cd frontend && npm run dev` (Vite on :5173, proxies `/api` to the backend)
- Assistant (Kilo): needs Ollama on 127.0.0.1:11434 with `ASSISTANT_MODEL` pulled (default `qwen3.5:4b-q4_K_M`). Backend tests stub Ollama out.
- Verify frontend: `cd frontend && npx vite build` (no test suite or linter is configured)
- Restart the Vite dev server after editing `tailwind.config.js`; a running server keeps the old config and fails on new classes.

## Frontend styling conventions
- Light and dark themes come from CSS variables in `frontend/src/App.css` (`:root` = light, `.dark` = dark), mapped to Tailwind colours in `tailwind.config.js`: `canvas`, `surface`, `sunken`, `line`, `line-strong`, `ink` / `ink-soft` / `ink-muted`, `accent` (electric blue), `volt` (energy yellow: fills and icons, not body text in light mode), `pos`, `warn`, `neg`, `viz-*`.
- The UI scales with the window on screens 1024px and wider (root font size in `App.css`: 16px at 1710px wide, 13px to 18px), so the layout looks the same on a MacBook and on a Windows laptop at 125% or 150% scaling. Size things in rem (Tailwind spacing, `max-w-[17.5rem]`), not px. Use `text-2xs` (not `text-[11px]`) for the smallest text; it and `text-xs` never drop below 11px.
- Use those tokens only. Do not use raw palette classes (`slate-*`, `sky-*`, `text-white`, `bg-black/…`) or hex colours in components.
- Charts and SVG: use `color("viz-blue")` / `color("ink", 0.04)` from `src/theme.jsx`, which emits `rgb(var(--…))` so charts follow the theme.
- Theme preference (System / Light / Dark) lives in `ThemeProvider` (`src/theme.jsx`), stored in `localStorage["watttrace-theme"]`; `index.html` applies it before first paint.
- Shared component classes in `App.css`: `dash-card`, `stat-card`, `inset-panel`, `card-title`, `card-sub`, `eyebrow`, `tech-tag(-live|-sim|-alert|-pos|-neutral)`, `btn`, `btn-primary`, `btn-icon`, `link`, `seg` / `seg-item(-active)`, `field-input`, `th`.
- Motion lives in `App.css` (Motion section) and `src/motion.jsx`: `stagger` (children rise in one by one), `animate-pop-in` / `animate-fade-in` (dialogs, popovers), `meter` (bars charge up and glide), `current-flow` (dashes moving along an SVG path, speed tied to load), `reading-flash` with `useChangeKey` (one-shot on a fresh reading), and `useTween` / `<Counter>` (figures count to their value). Motion must carry meaning (arrival, change, load); everything is switched off under `prefers-reduced-motion`.
- Style: sentence case, DM Sans everywhere with `tabular-nums` for figures (monospace only for code), minimum text size 11px, no glows, gradients or decorative looping animation, no `select-none` on content.
- Never pair coloured text with a tinted background of the same hue (e.g. `text-pos bg-pos/10`). Status pills stay neutral (`border-line bg-surface text-ink-soft`); the status colour goes only on a small dot or a leading icon (what `tech-tag-*` does).
