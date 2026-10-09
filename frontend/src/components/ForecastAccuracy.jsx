import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Crosshair, Target, CheckCircle2, Sigma, Loader2 } from "lucide-react";
import { Counter } from "../motion";

// The fine-tuned ARIMA models scored on their held-out windows as an "in use / idle" classifier
// (backend /api/forecast/accuracy, training wattcast/classify.py). Re-read every minute, so a new
// fine-tuning run shows up without a reload.
const POLL_MS = 60_000;

const pct = (v) => (v == null ? "–" : `${(v * 100).toFixed(1)}%`);
const whLabel = (wh) => `${wh} Wh/h`;
const timeOf = (iso) =>
  iso ? new Date(iso.replace(" ", "T")).toLocaleString("en-PH", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";

function Tile({ title, icon: Icon, value, sub, foot, valueClass = "text-ink" }) {
  return (
    <div className="stat-card flex flex-col justify-between min-w-0">
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="eyebrow">{title}</span>
          <Icon className="w-4 h-4 shrink-0 text-ink-muted" />
        </div>
        <div className={`stat-value truncate ${valueClass}`}>
          {value == null ? "–" : <Counter value={value * 100} format={(v) => `${v.toFixed(1)}%`} />}
        </div>
        <div className="text-xs text-ink-muted mt-2 leading-snug">{sub}</div>
      </div>
      <div className="mt-4 pt-3 border-t border-line text-xs text-ink-soft truncate" title={foot}>
        {foot}
      </div>
    </div>
  );
}

function F1Bar({ value }) {
  return (
    <div className="meter w-20 h-1.5 bg-line rounded-full overflow-hidden">
      <div className="h-full bg-accent rounded-full" style={{ width: `${(value ?? 0) * 100}%` }} />
    </div>
  );
}

function Confusion({ s }) {
  const cell = (label, n, hint) => (
    <div className="inset-panel px-3 py-2 min-w-0">
      <div className="text-[11px] text-ink-muted truncate">{label}</div>
      <div className="text-lg font-bold tabular-nums text-ink">{n}</div>
      <div className="text-[11px] leading-snug text-ink-muted">{hint}</div>
    </div>
  );
  return (
    <div className="grid grid-cols-2 gap-2">
      {cell("True positive", s.tp, "In use, forecast in use")}
      {cell("False positive", s.fp, "Idle, forecast in use")}
      {cell("False negative", s.fn, "In use, forecast idle")}
      {cell("True negative", s.tn, "Idle, forecast idle")}
    </div>
  );
}

export default function ForecastAccuracy() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [usedWh, setUsedWh] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .forecastAccuracy()
        .then((d) => alive && (setData(d), setError(null)))
        .catch((e) => alive && setError(e.message));
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!data && !error) {
    return (
      <section className="dash-card p-5 text-sm text-ink-muted flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> Scoring the fine-tuned models…
      </section>
    );
  }
  if (error || !data.available) {
    return (
      <section className="dash-card p-5 min-w-0">
        <h2 className="card-title">Forecast accuracy</h2>
        <p className="card-sub mt-1">{error || data.reason}</p>
      </section>
    );
  }

  const thresholds = data.thresholds;
  const t = thresholds.find((x) => x.used_wh === (usedWh ?? data.default_used_wh)) || thresholds[0];
  const s = t.chosen;
  const naive = t.baselines["Seasonal naive"];
  const forecastInUse = s.tp + s.fp;
  const fewPositives = t.in_use_steps < 5;
  const agents = Object.entries(t.agents);

  return (
    <div className="space-y-6 min-w-0">
      <section className="dash-card p-5 min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="card-title">Is AI in use? Held-out forecasts, scored</h2>
            <div className="card-sub mt-0.5">
              Device {data.device_id} · fitted {timeOf(data.fitted)} on {data.data.known_hours} h of readings ·{" "}
              {t.steps} held-out 15-minute steps, {t.in_use_steps} in use
            </div>
          </div>
          <div className="flex flex-col items-start sm:items-end gap-1.5 max-w-full">
            <span className="eyebrow">Counts as in use from (default {whLabel(data.default_used_wh)})</span>
            <div className="seg overflow-x-auto max-w-full" role="tablist" aria-label="In-use threshold">
              {thresholds.map((x) => (
                <button
                  key={x.used_wh}
                  role="tab"
                  aria-selected={x === t}
                  onClick={() => setUsedWh(x.used_wh)}
                  className={`seg-item tabular-nums whitespace-nowrap ${x === t ? "seg-item-active" : ""}`}
                >
                  {whLabel(x.used_wh)}
                </button>
              ))}
            </div>
          </div>
        </div>
        {fewPositives && (
          <div className="mt-4 flex items-start gap-2 text-xs text-ink-soft">
            <span className="tech-tag tech-tag-sim shrink-0">Few in-use steps</span>
            <span className="leading-relaxed">
              Only {t.in_use_steps} held-out step{t.in_use_steps === 1 ? " was" : "s were"} in use, so precision, recall
              and F1 move a lot with one step. They firm up as the device reader collects more hours and the models
              are fine-tuned again.
            </span>
          </div>
        )}
      </section>

      <div className="stagger grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 min-w-0">
        <Tile
          title="Accuracy"
          icon={CheckCircle2}
          value={s.accuracy}
          sub={`${s.tp + s.tn} of ${s.steps} steps called right`}
          foot={`Always idle scores ${pct(t.always_idle.accuracy)}`}
        />
        <Tile
          title="Precision"
          icon={Crosshair}
          value={s.precision}
          sub={
            forecastInUse
              ? `${s.tp} of ${forecastInUse} steps forecast in use were`
              : "No step was forecast in use, so there is nothing to score"
          }
          foot={`Seasonal naive: ${pct(naive?.precision)}`}
        />
        <Tile
          title="Recall"
          icon={Target}
          value={s.recall}
          sub={t.in_use_steps ? `${s.tp} of ${t.in_use_steps} in-use steps caught` : "No step was in use"}
          foot={`Seasonal naive: ${pct(naive?.recall)}`}
        />
        <Tile
          title="F1 score"
          icon={Sigma}
          value={s.f1}
          sub="Balance of precision and recall, the score to watch"
          foot={`Seasonal naive: ${pct(naive?.f1)}`}
        />
      </div>

      <section className="dash-card p-5 min-w-0">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6 min-w-0">
          <div className="min-w-0">
            <h2 className="card-title">Every model tried, and the baselines</h2>
            <div className="card-sub mt-0.5">Same held-out windows for all of them</div>
            {agents.map(([agent, rows]) => (
              <div key={agent} className="mt-4 overflow-x-auto">
                {agents.length > 1 && <div className="eyebrow mb-1">{agent}</div>}
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line">
                      <th className="th text-left pl-0">Model</th>
                      <th className="th text-right">Accuracy</th>
                      <th className="th text-right">Precision</th>
                      <th className="th text-right">Recall</th>
                      <th className="th text-right">F1</th>
                      <th className="th" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.model} className="border-b border-line last:border-0">
                        <td className="py-2 pr-2 text-ink whitespace-nowrap">
                          <span className={r.kind === "baseline" ? "text-ink-soft" : "font-medium"}>{r.model}</span>
                          {r.chosen && <span className="tech-tag tech-tag-live ml-2">Picked</span>}
                          {r.kind === "baseline" && <span className="text-ink-muted"> · baseline</span>}
                        </td>
                        <td className="py-2 px-2 text-right tabular-nums text-ink">{pct(r.accuracy)}</td>
                        <td className="py-2 px-2 text-right tabular-nums text-ink">{pct(r.precision)}</td>
                        <td className="py-2 px-2 text-right tabular-nums text-ink">{pct(r.recall)}</td>
                        <td className="py-2 px-2 text-right tabular-nums font-semibold text-ink">{pct(r.f1)}</td>
                        <td className="py-2 pl-2">
                          <F1Bar value={r.f1} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-ink">Confusion matrix</h3>
            <div className="card-sub mt-0.5 mb-3">The picked model, all agents</div>
            <Confusion s={s} />
          </div>
        </div>
        <p className="mt-4 text-xs text-ink-muted leading-relaxed">
          The models forecast watt-hours per 15-minute step. Each held-out step, forecast and actual, counts as in use
          when it reaches {whLabel(t.used_wh)} ({t.per_step_wh.toFixed(4)} Wh per step). On a mostly idle machine
          accuracy looks high even for a model that never says "in use", which is why always idle is listed: compare F1.
        </p>
      </section>
    </div>
  );
}
