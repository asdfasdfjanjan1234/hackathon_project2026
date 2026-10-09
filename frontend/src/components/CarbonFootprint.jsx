import { Leaf, Cloud, Laptop, Target, TreePine, ArrowRight, AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import { formatCo2, formatKwh, shortDate, peso } from "../format";
import { CARBON_TERMS, explainCarbon } from "../explain";
import { color } from "../theme";
import CleanHours from "./CleanHours";
import EmissionsChart from "./EmissionsChart";
import Figures from "./Figures";
import KiloInsight from "./KiloInsight";
import { CardHeader, StatCard } from "./Card";

// Device vs data center: a green/violet pair that stays distinct in both themes.
const DEVICE = color("viz-green");
const DATACENTER = color("viz-violet");

// Kilo's inline explanation of the whole ledger. The backend hands it the figures; this asks for the reading.
const LEDGER_QUESTION =
  "Explain my Carbon Ledger in plain words for someone who isn't an engineer: how big my AI carbon footprint is " +
  "compared with everyday things, where most of it comes from, whether it is going up or down, and the one thing " +
  "worth doing. Quote every figure exactly as DATA writes it, without rounding. At most 4 short sentences.";

const BUDGET_STATUS = {
  under: { label: "On track", tag: "tech-tag-pos", icon: CheckCircle2 },
  fixed_by_recommendations: { label: "Over · fixed by recommendations", tag: "tech-tag-sim", icon: AlertTriangle },
  over: { label: "Over budget", tag: "tech-tag-alert", icon: AlertTriangle },
};

// Asks Kilo about one figure, from the corner of its card.
function AskButton({ ask, onAsk }) {
  if (!onAsk || !ask) return null;
  return (
    <button onClick={() => onAsk(ask)} className="btn-icon h-6 w-6" title={`Ask Kilo: ${ask}`} aria-label={`Ask Kilo: ${ask}`}>
      <Sparkles className="w-3.5 h-3.5" />
    </button>
  );
}

function BudgetMeter({ budget }) {
  // Fill to the projected share; a marker shows where the recommendations would land.
  const now = Math.min(budget.used_share, 1.5);
  const recs = Math.min(budget.used_share_with_recommendations, 1.5);
  const scale = (x) => `${(x / 1.5) * 100}%`;
  return (
    <div className="relative h-2 rounded-full bg-line mt-2.5" aria-hidden>
      <div
        className={`absolute inset-y-0 left-0 rounded-full ${budget.used_share > 1 ? "bg-neg" : "bg-pos"}`}
        style={{ width: scale(now) }}
      />
      <div className="absolute -top-1 -bottom-1 w-0.5 bg-ink" style={{ left: scale(1) }} title="Budget" />
      {recs < now && (
        <div className="absolute -top-1 -bottom-1 w-0.5 bg-pos" style={{ left: scale(recs) }} title="With recommendations" />
      )}
    </div>
  );
}

// The ledger in plain sentences (always there, instant), beside Kilo's own reading of it (on request).
function WhatItMeans({ carbon, params, range, onAsk }) {
  const lines = explainCarbon(carbon);
  const { totals, cycle, budget, insights } = carbon;
  const cloudHeavy = (insights?.cloud_share ?? 0) >= 0.5;
  const followUps = [
    cloudHeavy ? "Why isn't cloud CO₂ on my electricity bill?" : "Why does a local model cause CO₂ here?",
    "How can I lower my AI carbon footprint?",
    "When is the cleanest time to run AI?",
  ];
  return (
    <section className="dash-card p-5 min-w-0">
      <CardHeader title="What this means" sub="The numbers on this page, in plain words" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-4 min-w-0">
        <ul className="space-y-2.5 min-w-0">
          {lines.map((l) => (
            <li key={l.key} className="flex gap-2.5 text-sm text-ink-soft leading-relaxed">
              <span className="w-1.5 h-1.5 rounded-full bg-ink-muted mt-2 shrink-0" aria-hidden />
              <span>
                <Figures text={l.text} />
              </span>
            </li>
          ))}
        </ul>
        <KiloInsight
          params={params}
          range={range}
          view="carbon"
          question={LEDGER_QUESTION}
          cacheKey={`${range}|${totals.total_kg}|${cycle.projected_kg}|${budget?.kg ?? 0}`}
          followUps={followUps}
          onAsk={onAsk}
        />
      </div>
    </section>
  );
}

function Glossary() {
  return (
    <details className="dash-card p-5 min-w-0 group">
      <summary className="flex items-center justify-between gap-3 cursor-pointer list-none">
        <span className="min-w-0">
          <span className="card-title block">What the terms mean</span>
          <span className="card-sub block mt-0.5">CO₂, grid factor, budgets and the rest</span>
        </span>
        <span className="link group-open:hidden">Show</span>
        <span className="link hidden group-open:inline-flex">Hide</span>
      </summary>
      <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 mt-4 pt-4 border-t border-line">
        {CARBON_TERMS.map((t) => (
          <div key={t.term} className="min-w-0">
            <dt className="text-sm font-semibold text-ink">{t.term}</dt>
            <dd className="text-xs text-ink-soft leading-relaxed mt-0.5">{t.text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

export default function CarbonFootprint({ carbon, params, range, onAsk, onOpenRecommendations }) {
  if (!carbon) return null;
  const { totals, cycle, budget, year, by_model: models = [], top_actions: actions = [], factors, window } = carbon;
  const status = budget && BUDGET_STATUS[budget.status];
  const cut = cycle.projected_kg - cycle.projected_kg_with_recommendations;
  // The long tail of tiny runtimes folds into one row.
  const shown = models.slice(0, 8);
  const rest = models.slice(8);

  return (
    <div className="space-y-6 min-w-0">
      {/* Headline tiles */}
      <div className="stagger grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 min-w-0">
        <StatCard
          title={`AI footprint · ${window?.short}`}
          icon={Leaf}
          value={totals.total_kg}
          format={formatCo2}
          sub={`${formatCo2(totals.device_kg)} on this device · ${formatCo2(totals.datacenter_kg)} in data centers`}
          foot={`≈ ${totals.trees_month} trees absorbing for a month`}
          action={
            <AskButton
              onAsk={onAsk}
              ask={`My AI footprint is ${formatCo2(totals.total_kg)} ${window?.label?.toLowerCase()}. Is that a lot, and where does it come from?`}
            />
          }
        />
        <StatCard
          title="This cycle (projected)"
          icon={Target}
          value={cycle.projected_kg}
          format={formatCo2}
          sub={`${shortDate(cycle.start)} – ${shortDate(cycle.end)}`}
          foot={cut > 0 ? `With recommendations: ${formatCo2(cycle.projected_kg_with_recommendations)}` : "No CO₂ cuts found"}
          tag={cut > 0 ? `-${formatCo2(cut)}` : null}
          tagClass="tech-tag-pos"
          action={
            <AskButton
              onAsk={onAsk}
              ask={`What does ${formatCo2(cycle.projected_kg)} projected this cycle mean, and how would the recommendations lower it?`}
            />
          }
        />
        <StatCard
          title="Carbon budget"
          icon={status?.icon || Target}
          value={budget ? budget.used_share * 100 : null}
          format={(v) => (v == null ? "Off" : `${Math.round(v)}%`)}
          sub={
            budget ? (
              <>
                of {budget.kg} kg CO₂ this cycle
                {budget.exceeded_on && ` · passed on ${shortDate(budget.exceeded_on)}`}
                <BudgetMeter budget={budget} />
              </>
            ) : (
              "Set a monthly CO₂ budget in Tariff & bill"
            )
          }
          foot={budget ? `With recommendations: ${Math.round(budget.used_share_with_recommendations * 100)}%` : "—"}
          tag={status?.label}
          tagClass={status?.tag}
          action={
            <AskButton
              onAsk={onAsk}
              ask={
                budget
                  ? `Am I on track with my carbon budget? This cycle is at ${Math.round(budget.used_share * 100)}% of it.`
                  : "What is a carbon budget, and should I set one?"
              }
            />
          }
        />
        <StatCard
          title="Avoided over 12 months"
          icon={TreePine}
          value={year.avoided_kg}
          format={formatCo2}
          sub={`${formatCo2(year.projected_kg)} → ${formatCo2(year.projected_kg_with_recommendations)} a year`}
          foot={`= ${year.trees_equivalent} trees for a year`}
          action={
            <AskButton
              onAsk={onAsk}
              ask={`What does ${formatCo2(year.avoided_kg)} avoided over 12 months mean, and what do I have to do to get it?`}
            />
          }
        />
      </div>

      <WhatItMeans carbon={carbon} params={params} range={range} onAsk={onAsk} />

      <EmissionsChart carbon={carbon} onAsk={onAsk} />

      <CleanHours info={carbon.clean_hours} />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-w-0">
        {/* Per-model footprint */}
        <section className="dash-card p-5 lg:col-span-7 min-w-0">
          <CardHeader title="Footprint by model" sub={`CO₂ per model, ${window?.label?.toLowerCase()}`} />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse min-w-[520px] whitespace-nowrap">
              <thead>
                <tr className="border-b border-line">
                  <th className="th">Model</th>
                  <th className="th">Where</th>
                  <th className="th text-right">Energy</th>
                  <th className="th text-right">CO₂</th>
                  <th className="th text-right">Share</th>
                  <th className="th text-right" title="CO₂ per hour the model was working">
                    g/h
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {models.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-ink-muted">
                      No AI energy recorded in this window.
                    </td>
                  </tr>
                )}
                {shown.map((m) => (
                  <tr key={`${m.scope}|${m.model}`} className="hover:bg-sunken">
                    <td className="py-2.5 px-2 font-medium text-ink truncate max-w-[240px]" title={m.model}>
                      {m.model.replace(/^Claude Code · claude-/, "Claude Code · ")}
                    </td>
                    <td className="py-2.5 px-2">
                      <span className="inline-flex items-center gap-1.5 text-ink-soft text-xs">
                        {m.scope === "device" ? (
                          <Laptop className="w-3.5 h-3.5" style={{ color: DEVICE }} />
                        ) : (
                          <Cloud className="w-3.5 h-3.5" style={{ color: DATACENTER }} />
                        )}
                        {m.scope === "device" ? "Device" : "Data center"}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-right tabular-nums text-ink-soft">{formatKwh(m.kwh)}</td>
                    <td className="py-2.5 px-2 text-right tabular-nums text-ink font-semibold">{formatCo2(m.co2_kg)}</td>
                    <td className="py-2.5 px-2">
                      <div className="flex items-center justify-end gap-2">
                        <div className="meter w-16 h-1.5 rounded-full bg-line overflow-hidden" aria-hidden>
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${Math.max(m.share * 100, 2)}%`, backgroundColor: m.scope === "device" ? DEVICE : DATACENTER }}
                          />
                        </div>
                        <span className="w-9 text-right tabular-nums text-ink-soft">{Math.round(m.share * 100)}%</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-2 text-right tabular-nums text-ink-muted">
                      {m.g_per_active_hour ?? "—"}
                    </td>
                  </tr>
                ))}
                {rest.length > 0 && (
                  <tr>
                    <td colSpan={6} className="py-2.5 px-2 text-xs text-ink-muted">
                      + {rest.length} more, {formatCo2(rest.reduce((s, m) => s + m.co2_kg, 0))} together
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Biggest CO₂ cuts from the recommendations */}
        <section className="dash-card p-5 lg:col-span-5 min-w-0 flex flex-col">
          <CardHeader title="Biggest CO₂ cuts" sub="The recommendations that avoid the most CO₂ a month" />
          <div className="space-y-2.5 my-4 flex-1">
            {actions.length === 0 ? (
              <div className="empty-state">No recommendation cuts CO₂ right now.</div>
            ) : (
              actions.map((a) => (
                <div key={`${a.rule}|${a.model}`} className="p-3 inset-panel">
                  <div className="flex items-start justify-between gap-2 text-sm">
                    <span className="text-ink font-semibold min-w-0">
                      {a.action}: {a.model}
                    </span>
                    <span className="text-pos font-bold tabular-nums shrink-0">-{formatCo2(a.co2_saved_kg)} / mo</span>
                  </div>
                  <p className="text-xs text-ink-soft mt-1 leading-relaxed">
                    <Figures text={a.message} />
                  </p>
                  <p className="text-xs text-ink-muted mt-1">
                    {a.scope === "datacenter"
                      ? "Data-center CO₂ · not on your bill"
                      : a.scope === "carbon"
                      ? "Same energy, cleaner hours · bill unchanged"
                      : `Also saves ${peso(a.monthly_savings)} / mo`}
                  </p>
                </div>
              ))
            )}
          </div>
          <button onClick={onOpenRecommendations} className="link self-start">
            All recommendations <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </section>
      </div>

      <Glossary />

      <div className="text-xs text-ink-muted flex flex-wrap justify-between gap-2 pt-1">
        <span>
          Device: {factors.device_kg_per_kwh} kg CO₂/kWh ({factors.co2_source})
        </span>
        <span>
          Data center: {factors.datacenter_kg_per_kwh} kg CO₂/kWh ({factors.datacenter_source}) · cloud energy is estimated from tokens
        </span>
      </div>
    </div>
  );
}
