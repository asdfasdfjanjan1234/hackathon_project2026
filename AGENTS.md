# AGENTS.md

## Run
- Backend: `cd backend && source .venv/bin/activate && python run.py` (Flask on 127.0.0.1:5001)
- Frontend: `cd frontend && npm run dev` (Vite on :5173, proxies `/api` to the backend)
- Verify frontend: `cd frontend && npx vite build` (no test suite or linter is configured)
- Restart the Vite dev server after editing `tailwind.config.js`; a running server keeps the old config and fails on new classes.

## Frontend styling conventions
- Light and dark themes come from CSS variables in `frontend/src/App.css` (`:root` = light, `.dark` = dark), mapped to Tailwind colours in `tailwind.config.js`: `canvas`, `surface`, `sunken`, `line`, `line-strong`, `ink` / `ink-soft` / `ink-muted`, `accent`, `pos`, `warn`, `neg`, `viz-*`.
- Use those tokens only. Do not use raw palette classes (`slate-*`, `sky-*`, `text-white`, `bg-black/…`) or hex colours in components.
- Charts and SVG: use `color("viz-blue")` / `color("ink", 0.04)` from `src/theme.jsx`, which emits `rgb(var(--…))` so charts follow the theme.
- Theme preference (System / Light / Dark) lives in `ThemeProvider` (`src/theme.jsx`), stored in `localStorage["watttrace-theme"]`; `index.html` applies it before first paint.
- Shared component classes in `App.css`: `dash-card`, `stat-card`, `inset-panel`, `card-title`, `card-sub`, `eyebrow`, `tech-tag(-live|-sim|-alert|-pos|-neutral)`, `btn`, `btn-primary`, `btn-icon`, `link`, `seg` / `seg-item(-active)`, `field-input`, `th`.
- Style: sentence case, DM Sans everywhere with `tabular-nums` for figures (monospace only for code), minimum text size 11px, no glows, gradients or decorative pulsing, no `select-none` on content.
