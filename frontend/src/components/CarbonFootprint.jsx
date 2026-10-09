import { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Leaf, Cloud, Laptop, Target, TreePine, ArrowRight, AlertTriangle, CheckCircle2 } from "lucide-react";
import { formatCo2, formatKwh, shortDate, peso } from "../format";

// Validated pair (dataviz validator, dark surface #121927): device vs data center.
const DEVICE = "#059669";
const DATACENTER = "#6366F1";
const SURFACE = "#121927";

const BUDGET_STATUS = {
  under: { label: "ON TRACK", tag: "tech-tag-neutral", icon: CheckCircle2 },
  fixed_by_recommendations: { label: "OVER · FIXED BY DIRECTIVES", tag: "tech-tag-sim", icon: AlertTriangle },
  over: { label: "OVER BUDGET", tag: "tech-tag-alert", icon: AlertTriangle },
};

function Tile({ title, icon: Icon, value, subtext, footer, tag, tagClass = "tech-tag-neutral" }) {
  return (
    <div className="stat-card flex flex-col justify-between min-w-0">
      <div>
        <div className="flex items-center justify-between mb-2 gap-2">
          <span className="text-[10px] font-mono tracking-wider uppercase text-slate-400 truncate">{title}</span>
          <Icon className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
        </div>
        <div className="text-2xl font-mono font-bold tracking-tight text-white tabular-nums truncate">{value}</div>
        <div className="text-[11px] text-slate-400 mt-1">{subtext}</div>
      </div>
      <div className="mt-3 pt-2.5 border-t border-white/5 flex items-center justify-between text-xs font-mono gap-2">
        <span className="text-[10px] sm:text-[11px] text-slate-400 leading-snug">{footer}</span>
        {tag && <span className={`tech-tag shrink-0 ${tagClass}`}>{tag}</span>}
      </div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <div className="rounded bg-slate-950 border border-white/10 p-2.5 shadow-2xl text-xs font-mono min-w-[180px]">
      <div className="font-bold text-slate-300 pb-1 mb-1 border-b border-white/10 text-[11px]">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-3 text-[11px]">
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: p.color }} />
            {p.name}
          </span>
          <span className="font-bold text-white tabular-nums">{formatCo2(p.value)}</span>
        </div>
      ))}
      <div className="flex justify-between gap-3 text-[11px] pt-1 mt-1 border-t border-white/10">
        <span className="text-slate-400">Total</span>
        <span className="font-bold text-white tabular-nums">{formatCo2(total)}</span>
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
    <div className="relative h-2 rounded-full bg-white/[0.06] mt-2" aria-hidden>
      <div
        className={`absolute inset-y-0 left-0 rounded-full ${budget.used_share > 1 ? "bg-rose-500" : "bg-emerald-600"}`}
        style={{ width: scale(now) }}
      />
      <div className="absolute -top-1 -bottom-1 w-0.5 bg-slate-200" style={{ left: scale(1) }} title="Budget" />
      {recs < now && (
        <div className="absolute -top-1 -bottom-1 w-0.5 bg-emerald-300" style={{ left: scale(recs) }} title="With directives" />
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
    <div className="space-y-5 min-w-0">
      {/* Headline tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 min-w-0">
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
      <section className="dash-card p-4 sm:p-5 min-w-0">
        <div className="flex flex-wrap items-center justify-between pb-3 border-b border-white/5 gap-2">
          <div className="min-w-0">
            <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider">Daily AI Emissions</h2>
            <div className="text-[10px] text-slate-400">{window?.label} · kg CO₂ per day</div>
          </div>
          <div className="flex items-center gap-3 text-[11px] font-mono text-slate-300">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: DEVICE }} /> This device
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: DATACENTER }} /> Cloud data centers
            </span>
          </div>
        </div>
        <div className="h-56 mt-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 4, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="2 2" stroke="rgba(255, 255, 255, 0.05)" vertical={false} />
              <XAxis dataKey="day" stroke="#64748B" fontSize={10} tickLine={false} axisLine={false} minTickGap={16} />
              <YAxis
                stroke="#64748B"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => (v >= 1 ? `${v.toFixed(1)}kg` : `${Math.round(v * 1000)}g`)}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="This device" stackId="co2" fill={DEVICE} stroke={SURFACE} strokeWidth={2} />
              <Bar
                dataKey="Cloud data centers"
                stackId="co2"
                fill={DATACENTER}
                stroke={SURFACE}
                strokeWidth={2}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-w-0">
        {/* Per-model footprint */}
        <section className="dash-card p-4 sm:p-5 lg:col-span-7 min-w-0">
          <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider pb-3 border-b border-white/5">
            Footprint by Model
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse min-w-[520px] font-mono whitespace-nowrap">
              <thead>
                <tr className="border-b border-white/5 text-slate-400 uppercase tracking-wider text-[10px]">
                  <th className="py-2.5 px-2 font-bold">Model</th>
                  <th className="py-2.5 px-2 font-bold">Where</th>
                  <th className="py-2.5 px-2 font-bold text-right">Energy</th>
                  <th className="py-2.5 px-2 font-bold text-right">CO₂</th>
                  <th className="py-2.5 px-2 font-bold text-right">Share</th>
                  <th className="py-2.5 px-2 font-bold text-right" title="CO₂ per hour the model was working">
                    g/h
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {models.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-400">
                      No AI energy recorded in this window.
                    </td>
                  </tr>
                )}
                {shown.map((m) => (
                  <tr key={`${m.scope}|${m.model}`} className="hover:bg-white/[0.02]">
                    <td className="py-2.5 px-2 text-slate-200 truncate max-w-[240px]" title={m.model}>
                      {m.model.replace(/^Claude Code · claude-/, "Claude Code · ")}
                    </td>
                    <td className="py-2.5 px-2">
                      <span className="inline-flex items-center gap-1.5 text-slate-300">
                        {m.scope === "device" ? (
                          <Laptop className="w-3 h-3" style={{ color: DEVICE }} />
                        ) : (
                          <Cloud className="w-3 h-3" style={{ color: DATACENTER }} />
                        )}
                        {m.scope === "device" ? "Device" : "Data center"}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-right tabular-nums text-slate-300">{formatKwh(m.kwh)}</td>
                    <td className="py-2.5 px-2 text-right tabular-nums text-white font-bold">{formatCo2(m.co2_kg)}</td>
                    <td className="py-2.5 px-2 text-right tabular-nums text-slate-300">{Math.round(m.share * 100)}%</td>
                    <td className="py-2.5 px-2 text-right tabular-nums text-slate-400">
                      {m.g_per_active_hour ?? "—"}
                    </td>
                  </tr>
                ))}
                {rest.length > 0 && (
                  <tr>
                    <td colSpan={6} className="py-2.5 px-2 text-[11px] text-slate-400">
                      + {rest.length} more, {formatCo2(rest.reduce((s, m) => s + m.co2_kg, 0))} together
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Biggest CO₂ cuts from the directives */}
        <section className="dash-card p-4 sm:p-5 lg:col-span-5 min-w-0 flex flex-col">
          <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider pb-3 border-b border-white/5">
            Biggest CO₂ Cuts
          </h2>
          <div className="space-y-2.5 my-3 flex-1">
            {actions.length === 0 ? (
              <div className="p-4 text-center text-slate-400 text-xs">No directive cuts CO₂ right now.</div>
            ) : (
              actions.map((a) => (
                <div key={`${a.rule}|${a.model}`} className="p-3 rounded border border-white/5 bg-black/30">
                  <div className="flex items-center justify-between gap-2 text-xs font-mono">
                    <span className="text-sky-400 font-bold truncate">
                      {a.action}: {a.model}
                    </span>
                    <span className="text-emerald-300 font-bold tabular-nums shrink-0">-{formatCo2(a.co2_saved_kg)} / mo</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">{a.message}</p>
                  <p className="text-[10px] text-slate-400 mt-1 font-mono">
                    {a.scope === "datacenter" ? "Data-center CO₂ · not on your bill" : `Also saves ${peso(a.monthly_savings)} / mo`}
                  </p>
                </div>
              ))
            )}
          </div>
          <button
            onClick={onOpenDirectives}
            className="self-start text-[11px] font-mono font-bold text-sky-300 hover:text-sky-200 flex items-center gap-1.5"
          >
            ALL LOAD DIRECTIVES <ArrowRight className="w-3 h-3" />
          </button>
        </section>
      </div>

      <div className="text-[10px] font-mono text-slate-400 flex flex-wrap justify-between gap-2">
        <span>
          DEVICE: {factors.device_kg_per_kwh} kg CO₂/kWh ({factors.co2_source})
        </span>
        <span>
          DATA CENTER: {factors.datacenter_kg_per_kwh} kg CO₂/kWh ({factors.datacenter_source}) · cloud energy is estimated from tokens
        </span>
      </div>
    </div>
  );
}
