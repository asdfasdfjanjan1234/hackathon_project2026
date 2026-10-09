import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { peso, formatKwh, formatCo2, formatDuration } from "../format";
import { color } from "../theme";
import { Leaf, Smartphone, Car, Wind } from "lucide-react";

const VERDICT_CONFIG = {
  major: {
    status: "Major driver",
    desc: "Empirical telemetry confirms AI local GPU/CPU workload accounts for ≥50% of the bill increase.",
    badgeClass: "tech-tag-alert",
  },
  contributing: {
    status: "Partial driver",
    desc: "AI explains 20% to 50% of monthly variance; baseline appliances share attribution.",
    badgeClass: "tech-tag-sim",
  },
  minor: {
    status: "Negligible",
    desc: "AI workload accounts for <20% of bill increase. Primary surge is non-AI appliances.",
    badgeClass: "tech-tag-neutral",
  },
  none: {
    status: "Zero impact",
    desc: "Zero local hardware energy increase detected for AI processes.",
    badgeClass: "tech-tag-pos",
  },
  no_increase: {
    status: "Stable cycle",
    desc: "Current billing cycle does not exceed baseline consumption.",
    badgeClass: "tech-tag-pos",
  },
};

function EqTile({ icon: Icon, label, value, sub }) {
  return (
    <div className="p-3 inset-panel flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-xs text-ink-muted">
        <Icon className="w-3.5 h-3.5" />
        <span>{label}</span>
      </div>
      <div className="text-base font-semibold text-ink tabular-nums">{value}</div>
      <div className="text-[11px] text-ink-muted">{sub}</div>
    </div>
  );
}

export default function BillImpact({ impact }) {
  const safeImpact = impact || {};
  const verdict = VERDICT_CONFIG[safeImpact.verdict] || VERDICT_CONFIG.none;
  const eq = safeImpact.equivalents;

  const donutData = useMemo(
    () => [
      { name: "Local AI Metal/CUDA Draw", value: safeImpact.ai_effect, color: color("accent") },
      { name: "Utility Rate Hike", value: safeImpact.rate_effect, color: color("viz-grey") },
      { name: "Base Non-AI Household", value: safeImpact.other_effect, color: color("viz-amber") },
    ].filter((item) => item.value > 0),
    [safeImpact]
  );
  // No increase over the baseline: an empty ring, not a made-up slice.
  const ringData = donutData.length > 0 ? donutData : [{ name: "No increase", value: 1, color: color("line"), empty: true }];

  const totalIncrease = Math.max(1, safeImpact.increase || 1);
  if (!impact) return <section className="dash-card p-5 h-72 animate-pulse" />;
  const aiSharePct = ((safeImpact.ai_share || 0) * 100).toFixed(1);

  const CustomDonutTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const item = payload[0];
    const pct = ((item.value / totalIncrease) * 100).toFixed(1);
    return (
      <div className="rounded-lg bg-surface border border-line p-2.5 shadow-pop text-xs">
        <div className="flex items-center gap-1.5 mb-1 text-ink-soft">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.payload.color }} />
          <span>{item.name}</span>
        </div>
        <div className="text-ink-muted">
          Surcharge: <strong className="text-ink tabular-nums">{peso(item.value)}</strong> ({pct}%)
        </div>
      </div>
    );
  };

  return (
    <section className="dash-card p-5 flex flex-col justify-between min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-2">
        <div className="min-w-0">
          <h2 className="card-title">Causal tariff decomposition</h2>
          <div className="card-sub mt-0.5 tabular-nums">Factor analysis: +{peso(safeImpact.increase)} total variance</div>
        </div>
        <span className={`tech-tag shrink-0 ${verdict.badgeClass}`}>{verdict.status}</span>
      </div>

      {/* Main Grid: Donut + Causal Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-center my-4 min-w-0">
        {/* Left: Donut Chart */}
        <div className="md:col-span-5 relative flex items-center justify-center h-48 min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              {donutData.length > 0 && <Tooltip content={<CustomDonutTooltip />} />}
              <Pie
                data={ringData}
                cx="50%"
                cy="50%"
                innerRadius={56}
                outerRadius={76}
                paddingAngle={2}
                dataKey="value"
                stroke={color("surface")}
                strokeWidth={2}
              >
                {ringData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          {/* Center Callout */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-semibold text-ink tabular-nums tracking-tight">{aiSharePct}%</span>
            <span className="text-xs text-ink-muted">AI attributed</span>
          </div>
        </div>

        {/* Right: Analysis */}
        <div className="md:col-span-7 space-y-3 min-w-0">
          <div className="p-3 inset-panel space-y-1">
            <div className="text-sm font-semibold text-ink">
              {verdict.status}: {aiSharePct}% of surge
            </div>
            <p className="text-xs text-ink-soft leading-relaxed">
              {verdict.desc} AI apps and local models used {formatKwh(safeImpact.local_ai_kwh)} on this device
              ({peso(safeImpact.ai_effect)} of the increase)
              {eq && ` ≈ ${formatCo2(eq.co2_kg)}, or ${formatDuration(eq.aircon_hours)} of running a ${safeImpact.factors?.aircon_watts ?? "—"} W aircon`}.
            </p>
          </div>

          {/* Attribution Items */}
          <div className="divide-y divide-line">
            {donutData.length === 0 && (
              <div className="p-3 inset-panel text-xs text-ink-muted">
                This cycle's bill is not above the baseline, so there is nothing to attribute.
              </div>
            )}
            {donutData.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between py-2 text-sm">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                  <span className="text-ink-soft truncate">{item.name}</span>
                </div>
                <div className="flex items-center gap-2 tabular-nums shrink-0 ml-2">
                  <span className="text-ink-muted text-xs">{((item.value / totalIncrease) * 100).toFixed(0)}%</span>
                  <span className="font-semibold text-ink">{peso(item.value)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Environmental & Carbon Equivalencies */}
      {eq && (
        <div className="pt-4 border-t border-line space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="font-semibold text-ink flex items-center gap-1.5">
              <Leaf className="w-4 h-4 text-pos" />
              Green computing & eco equivalencies
            </span>
            {safeImpact.factors && (
              <span className="text-xs text-ink-muted" title={safeImpact.factors.co2_source}>
                Grid factor: {safeImpact.factors.co2_kg_per_kwh} kg CO₂/kWh
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <EqTile icon={Leaf} label="Emissions" value={formatCo2(eq.co2_kg)} sub="Carbon footprint" />
            <EqTile icon={Wind} label="Offset" value={`${eq.trees_offset || 0} Trees`} sub="Monthly absorption" />
            <EqTile icon={Smartphone} label="Phone draw" value={`${(eq.smartphone_charges || 0).toLocaleString()}x`} sub="Full battery charges" />
            <EqTile icon={Car} label="EV range" value={`${eq.ev_km || 0} km`} sub="EV highway equivalent" />
          </div>
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-line flex flex-wrap items-center justify-between text-xs text-ink-muted gap-2">
        <span>Cloud AI runs in provider data centers, so it isn't counted in your bill.</span>
        <span>Math: rate · AI · other usage decomposition</span>
      </div>
    </section>
  );
}
