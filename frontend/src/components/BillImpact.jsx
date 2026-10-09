import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { peso, formatKwh, formatCo2, formatDuration } from "../format";
import { color } from "../theme";
import { Leaf, Smartphone, Car, Wind } from "lucide-react";
import { CardHeader, MiniTile } from "./Card";

const VERDICT_CONFIG = {
  major: {
    status: "Major driver",
    desc: "AI on this computer explains half or more of the increase over your bill before AI.",
    badgeClass: "tech-tag-alert",
  },
  contributing: {
    status: "Partial driver",
    desc: "AI explains 20% to 50% of the increase; the rest comes from other use and the rate.",
    badgeClass: "tech-tag-sim",
  },
  minor: {
    status: "Small part",
    desc: "AI explains less than 20% of the increase. Most of it is other appliances or the rate.",
    badgeClass: "tech-tag-neutral",
  },
  none: {
    status: "No impact",
    desc: "AI on this computer added no measurable energy to the bill.",
    badgeClass: "tech-tag-pos",
  },
  no_increase: {
    status: "No increase",
    desc: "This cycle's bill isn't above your bill before AI.",
    badgeClass: "tech-tag-pos",
  },
};

export default function BillImpact({ impact }) {
  const safeImpact = impact || {};
  const verdict = VERDICT_CONFIG[safeImpact.verdict] || VERDICT_CONFIG.none;
  const eq = safeImpact.equivalents;

  const donutData = useMemo(
    () => [
      { name: "AI on this computer", value: safeImpact.ai_effect, color: color("accent") },
      { name: "Rate change", value: safeImpact.rate_effect, color: color("viz-grey") },
      { name: "Other household use", value: safeImpact.other_effect, color: color("viz-amber") },
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
          Adds <strong className="text-ink tabular-nums">{peso(item.value)}</strong> ({pct}%)
        </div>
      </div>
    );
  };

  return (
    <section className="dash-card p-5 flex flex-col justify-between min-w-0">
      <CardHeader
        title="Did AI raise my bill?"
        sub={`This month's bill is ${peso(safeImpact.increase)} above your bill before AI, split into rate change, AI and other use`}
      >
        <span className={`tech-tag ${verdict.badgeClass}`}>{verdict.status}</span>
      </CardHeader>

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
            <span className="text-2xl font-bold text-ink tabular-nums tracking-tight">{aiSharePct}%</span>
            <span className="text-xs text-ink-muted">AI attributed</span>
          </div>
        </div>

        {/* Right: Analysis */}
        <div className="md:col-span-7 space-y-3 min-w-0">
          <div className="p-3 inset-panel space-y-1">
            <div className="text-sm font-bold text-ink">
              {verdict.status}: {aiSharePct}% of the increase
            </div>
            <p className="text-xs text-ink-soft leading-relaxed">
              {verdict.desc} AI apps and local models used{" "}
              <strong className="font-semibold text-ink tabular-nums">{formatKwh(safeImpact.local_ai_kwh)}</strong> on this device
              (<strong className="font-semibold text-ink tabular-nums">{peso(safeImpact.ai_effect)}</strong> of the increase)
              {eq && ` ≈ ${formatCo2(eq.co2_kg)}, or ${formatDuration(eq.aircon_hours)} of running a ${safeImpact.factors?.aircon_watts ?? "—"} W aircon`}.
            </p>
          </div>

          {/* Attribution Items */}
          <div className="divide-y divide-line">
            {donutData.length === 0 && (
              <div className="empty-state">
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
              What that energy equals
            </span>
            {safeImpact.factors && (
              <span className="text-xs text-ink-muted" title={safeImpact.factors.co2_source}>
                Grid factor: {safeImpact.factors.co2_kg_per_kwh} kg CO₂/kWh
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <MiniTile icon={Leaf} title="Emissions" value={formatCo2(eq.co2_kg)} sub="Carbon footprint" />
            <MiniTile icon={Wind} title="Offset" value={`${eq.trees_offset || 0} trees`} sub="Absorbing for a month" />
            <MiniTile icon={Smartphone} title="Phone charges" value={`${(eq.smartphone_charges || 0).toLocaleString()}×`} sub="Full battery charges" />
            <MiniTile icon={Car} title="EV range" value={`${eq.ev_km || 0} km`} sub="Highway driving" />
          </div>
        </div>
      )}

      <div className="card-foot">
        <span>Cloud AI runs in provider data centers, so it isn't counted in your bill.</span>
      </div>
    </section>
  );
}
