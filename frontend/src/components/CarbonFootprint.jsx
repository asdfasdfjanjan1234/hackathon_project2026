import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Leaf, Cloud, Laptop, Target, TreePine, ArrowRight, AlertTriangle, CheckCircle2 } from "lucide-react";
import { formatCo2, formatKwh, shortDate, peso } from "../format";
import { color } from "../theme";
import CleanHours from "./CleanHours";
import Figures from "./Figures";

// Device vs data center: a green/violet pair that stays distinct in both themes.
const DEVICE = color("viz-green");
const DATACENTER = color("viz-violet");
const SURFACE = color("surface");
const AXIS = { tick: { fill: color("ink-muted"), fontSize: 11 }, tickLine: false, axisLine: false };

const BUDGET_STATUS = {
  under: { label: "On track", tag: "tech-tag-pos", icon: CheckCircle2 },
  fixed_by_recommendations: { label: "Over · fixed by directives", tag: "tech-tag-sim", icon: AlertTriangle },
  over: { label: "Over budget", tag: "tech-tag-alert", icon: AlertTriangle },
};

function Tile({ title, icon: Icon, value, subtext, footer, tag, tagClass = "tech-tag-neutral" }) {
  return (
    <div className="stat-card flex flex-col justify-between min-w-0">
      <div>
        <div className="flex items-center justify-between mb-3 gap-2">
          <span className="eyebrow truncate">{title}</span>
          <Icon className="w-4 h-4 text-ink-muted shrink-0" />
        </div>
        <div className="stat-value truncate text-ink">{value}</div>
        <div className="text-xs text-ink-muted mt-2 leading-snug">{subtext}</div>
      </div>
      <div className="mt-4 pt-3 border-t border-line flex items-center justify-between gap-2">
        <span className="text-xs text-ink-soft leading-snug">{footer}</span>
        {tag && <span className={`tech-tag shrink-0 ${tagClass}`}>{tag}</span>}
      </div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <div className="rounded-lg bg-surface border border-line p-2.5 shadow-pop text-xs min-w-[180px]">
      <div className="font-medium text-ink pb-1.5 mb-1.5 border-b border-line">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-ink-soft">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
            {p.name}
          </span>
          <span className="font-semibold text-ink tabular-nums">{formatCo2(p.value)}</span>
        </div>
      ))}
      <div className="flex justify-between gap-3 pt-1.5 mt-1.5 border-t border-line">
        <span className="text-ink-muted">Total</span>
        <span className="font-semibold text-ink tabular-nums">{formatCo2(total)}</span>
      </div>
    </div>
  );
}

function BudgetMeter({ budget }) {
  // Fill to the projected share; a marker shows where the directives would land.
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
        <div className="absolute -top-1 -bottom-1 w-0.5 bg-pos" style={{ left: scale(recs) }} title="With directives" />
      )}
    </div>
  );
}

export default function CarbonFootprint({ carbon, onOpenDirectives }) {
  const data = useMemo(
    () =>
      (carbon?.daily || []).map((d) => ({
        day: shortDate(d.date),
        "This device": d.device_kg,
        "Cloud data centers": d.datacenter_kg,
      })),
    [carbon]
  );

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
        <Tile
          title={`AI footprint · ${window?.short}`}
          icon={Leaf}
          value={formatCo2(totals.total_kg)}
          subtext={`${formatCo2(totals.device_kg)} on this device · ${formatCo2(totals.datacenter_kg)} in data centers`}
          footer={`≈ ${totals.trees_month} trees absorbing for a month`}
        />
        <Tile
          title="This cycle (projected)"
          icon={Target}
          value={formatCo2(cycle.projected_kg)}
          subtext={`${shortDate(cycle.start)} – ${shortDate(cycle.end)}`}
          footer={cut > 0 ? `With directives: ${formatCo2(cycle.projected_kg_with_recommendations)}` : "No CO₂ cuts found"}
          tag={cut > 0 ? `-${formatCo2(cut)}` : null}
          tagClass="tech-tag-pos"
        />
        <Tile
          title="Carbon budget"
          icon={status?.icon || Target}
          value={budget ? `${Math.round(budget.used_share * 100)}%` : "Off"}
          subtext={
            budget ? (
              <>
                of {budget.kg} kg CO₂ this cycle
                {budget.exceeded_on && ` · passed on ${shortDate(budget.exceeded_on)}`}
                <BudgetMeter budget={budget} />
              </>
            ) : (
              "Set a monthly CO₂ cap in Tariff & Hardware"
            )
          }
          footer={budget ? `With directives: ${Math.round(budget.used_share_with_recommendations * 100)}%` : "—"}
          tag={status?.label}
          tagClass={status?.tag}
        />
        <Tile
          title="Avoided over 12 months"
          icon={TreePine}
          value={formatCo2(year.avoided_kg)}
          subtext={`${formatCo2(year.projected_kg)} → ${formatCo2(year.projected_kg_with_recommendations)} a year`}
          footer={`= ${year.trees_equivalent} trees for a year`}
        />
      </div>

      {/* Daily CO₂, stacked by where it was emitted */}
      <section className="dash-card p-5 min-w-0">
        <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-2">
          <div className="min-w-0">
            <h2 className="card-title">Daily AI emissions</h2>
            <div className="card-sub mt-0.5">{window?.label} · kg CO₂ per day</div>
          </div>
          <div className="flex items-center gap-4 text-xs text-ink-soft">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: DEVICE }} /> This device
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: DATACENTER }} /> Cloud data centers
            </span>
          </div>
        </div>
        <div className="h-56 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 4, left: -8, bottom: 0 }}>
              <CartesianGrid stroke={color("line")} vertical={false} />
              <XAxis dataKey="day" {...AXIS} minTickGap={16} />
              <YAxis
                {...AXIS}
                tickFormatter={(v) => (v >= 1 ? `${v.toFixed(1)}kg` : `${Math.round(v * 1000)}g`)}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: color("ink", 0.04) }} />
              <Bar dataKey="This device" stackId="co2" fill={DEVICE} stroke={SURFACE} strokeWidth={1} />
              <Bar
                dataKey="Cloud data centers"
                stackId="co2"
                fill={DATACENTER}
                stroke={SURFACE}
                strokeWidth={1}
                radius={[3, 3, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <CleanHours info={carbon.clean_hours} />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-w-0">
        {/* Per-model footprint */}
        <section className="dash-card p-5 lg:col-span-7 min-w-0">
          <h2 className="card-title pb-4 border-b border-line">Footprint by model</h2>
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
                    <td className="py-2.5 px-2 text-right tabular-nums text-ink-soft">{Math.round(m.share * 100)}%</td>
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

        {/* Biggest CO₂ cuts from the directives */}
        <section className="dash-card p-5 lg:col-span-5 min-w-0 flex flex-col">
          <h2 className="card-title pb-4 border-b border-line">Biggest CO₂ cuts</h2>
          <div className="space-y-2.5 my-4 flex-1">
            {actions.length === 0 ? (
              <div className="p-4 text-center text-ink-muted text-sm">No directive cuts CO₂ right now.</div>
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
          <button onClick={onOpenDirectives} className="link self-start">
            All load directives <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </section>
      </div>

      <div className="text-xs text-ink-muted flex flex-wrap justify-between gap-2">
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
