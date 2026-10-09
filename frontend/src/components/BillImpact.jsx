import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { peso, formatKwh, formatCo2, formatDuration } from "../format";
import { PieChart as PieIcon } from "lucide-react";

const VERDICT_CONFIG = {
  major: {
    status: "MAJOR DRIVER",
    desc: "Empirical telemetry confirms AI local GPU/CPU workload accounts for ≥50% of the bill increase.",
    badgeClass: "bg-rose-500/10 text-rose-400 border-rose-500/25",
    color: "#F43F5E",
  },
  contributing: {
    status: "PARTIAL DRIVER",
    desc: "AI explains 20% to 50% of monthly variance; baseline appliances share attribution.",
    badgeClass: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    color: "#F59E0B",
  },
  minor: {
    status: "NEGLIGIBLE",
    desc: "AI workload accounts for <20% of bill increase. Primary surge is non-AI appliances.",
    badgeClass: "bg-sky-500/10 text-sky-400 border-sky-500/25", // Cyan, NO GREEN
    color: "#38BDF8",
  },
  none: {
    status: "ZERO IMPACT",
    desc: "Zero local hardware energy increase detected for AI processes.",
    badgeClass: "bg-sky-500/10 text-sky-400 border-sky-500/25",
    color: "#38BDF8",
  },
  no_increase: {
    status: "STABLE CYCLE",
    desc: "Current billing cycle does not exceed baseline consumption.",
    badgeClass: "bg-sky-500/10 text-sky-400 border-sky-500/25",
    color: "#38BDF8",
  },
};

export default function BillImpact({ impact }) {
  const safeImpact = impact || {};
  const verdict = VERDICT_CONFIG[safeImpact.verdict] || VERDICT_CONFIG.none;
  const eq = safeImpact.equivalents;

  const donutData = useMemo(() => {
    const raw = [
      { name: "Local AI Metal/CUDA Draw", value: safeImpact.ai_effect, color: "#F43F5E" },
      { name: "Utility Rate Hike", value: safeImpact.rate_effect, color: "#64748B" },
      { name: "Base Non-AI Household", value: safeImpact.other_effect, color: "#0284C7" },
    ].filter((item) => item.value > 0);

    return raw.length > 0 ? raw : [{ name: "Stable Load", value: 1, color: "#38BDF8" }];
  }, [safeImpact]);

  const totalIncrease = Math.max(1, safeImpact.increase || 1);
  if (!impact) return <section className="dash-card p-5 h-72 animate-pulse" />;
  const aiSharePct = ((safeImpact.ai_share || 0) * 100).toFixed(1);

  const CustomDonutTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;
    const item = payload[0];
    const pct = ((item.value / totalIncrease) * 100).toFixed(1);
    return (
      <div className="rounded bg-slate-950 border border-white/10 p-2 shadow-xl text-xs font-mono">
        <div className="flex items-center gap-1.5 mb-1 text-slate-300">
          <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: item.payload.color }} />
          <span>{item.name}</span>
        </div>
        <div className="text-slate-400">
          Surcharge: <strong className="text-white tabular-nums">{peso(item.value)}</strong> ({pct}%)
        </div>
      </div>
    );
  };

  return (
    <section className="dash-card p-4 sm:p-5 flex flex-col justify-between select-none min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-white/5 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <PieIcon className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider truncate">
              Causal Tariff Decomposition
            </h2>
            <div className="text-[10px] font-mono text-slate-400 truncate">
              Factor Analysis: +{peso(safeImpact.increase)} Total Variance
            </div>
          </div>
        </div>

        {/* Verdict Badge */}
        <span
          className={`tech-tag shrink-0 ${verdict.badgeClass}`}
        >
          {verdict.status}
        </span>
      </div>

      {/* Main Grid: Donut + Causal Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center my-3 min-w-0">
        {/* Left: Donut Chart */}
        <div className="md:col-span-5 relative flex items-center justify-center h-44 sm:h-48 min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip content={<CustomDonutTooltip />} />
              <Pie
                data={donutData}
                cx="50%"
                cy="50%"
                innerRadius={52}
                outerRadius={74}
                paddingAngle={3}
                dataKey="value"
                stroke="#101624"
                strokeWidth={2}
              >
                {donutData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>

          {/* Center Callout */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-mono font-extrabold text-white tabular-nums tracking-tight">
              {aiSharePct}%
            </span>
            <span className="text-[9px] font-mono uppercase tracking-widest text-slate-400">
              AI ATTRIBUTED
            </span>
          </div>
        </div>

        {/* Right: Telemetry Analysis Panel */}
        <div className="md:col-span-7 space-y-2.5 min-w-0">
          <div className="p-2.5 rounded bg-black/30 border border-white/5 space-y-1 font-mono text-xs">
            <div className="text-[11px] font-bold text-slate-200">
              {verdict.status}: {aiSharePct}% of Surge
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
              {verdict.desc} AI apps and local models used {formatKwh(safeImpact.local_ai_kwh)} on this device
              ({peso(safeImpact.ai_effect)} of the increase)
              {eq && ` ≈ ${formatCo2(eq.co2_kg)}, or ${formatDuration(eq.aircon_hours)} of running a 1 HP aircon`}.
            </p>
          </div>

          {/* Attribution Items */}
          <div className="space-y-1.5 font-mono text-xs">
            {donutData.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-1.5 rounded bg-white/[0.02] border border-white/5"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="w-2 h-2 rounded-sm shrink-0"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-slate-300 text-[11px] truncate">{item.name}</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] tabular-nums shrink-0 ml-2">
                  <span className="text-slate-400">
                    ({((item.value / totalIncrease) * 100).toFixed(0)}%)
                  </span>
                  <span className="font-bold text-slate-100">{peso(item.value)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Industrial Footnote */}
      <div className="pt-2.5 border-t border-white/5 flex flex-wrap items-center justify-between text-[10px] font-mono text-slate-400 gap-2">
        <span>Cloud AI runs in provider data centers, so it isn't counted in your bill.</span>
        <span className="text-slate-400">MATH: RATE · AI · OTHER USAGE DECOMPOSITION</span>
      </div>
    </section>
  );
}
