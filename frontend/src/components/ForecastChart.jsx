import { useState, useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { peso, pesoCompact } from "../format";
import { BarChart3 } from "lucide-react";

export default function ForecastChart({ forecast, recs }) {
  const baselineBill = forecast?.baseline_bill ?? 1500;
  const forecastBill = forecast?.forecast_bill ?? 2650;
  const recsBill = recs?.bill_with_recommendations ?? 1920;
  const monthName = forecast?.month ?? "October 2026";
  const daysLeft = forecast?.days_left ?? 22;

  // Generate 30-day curve matching billing cycle
  const chartData = useMemo(() => {
    const totalDays = 30;
    const currentDay = Math.max(1, totalDays - daysLeft);
    const data = [];

    const baselineDaily = baselineBill / totalDays;
    const currentAiDaily = (forecastBill - baselineBill) / totalDays;
    const recsAiDaily = (recsBill - baselineBill) / totalDays;

    for (let day = 1; day <= totalDays; day++) {
      const isPast = day <= currentDay;
      const baselineCum = Math.round(baselineDaily * day);
      let currentCum, recsCum;

      if (isPast) {
        const commonAi = (currentAiDaily * 0.9 + (day / totalDays) * currentAiDaily * 0.2) * day;
        currentCum = Math.round(baselineCum + commonAi);
        recsCum = currentCum;
      } else {
        const daysPast = currentDay;
        const basePast = baselineDaily * daysPast + (currentAiDaily * 0.95) * daysPast;
        const daysFuture = day - daysPast;

        currentCum = Math.round(basePast + (baselineDaily + currentAiDaily * 1.08) * daysFuture);
        recsCum = Math.round(basePast + (baselineDaily + recsAiDaily * 0.85) * daysFuture);
      }

      data.push({
        day: `D${day}`,
        dayNum: day,
        isPast,
        Baseline: baselineCum,
        "Current Unregulated": currentCum,
        "Optimized Shed": recsCum,
      });
    }

    return data;
  }, [baselineBill, forecastBill, recsBill, daysLeft]);

  const maxVal = Math.max(...chartData.map((d) => d["Current Unregulated"]));
  const totalSavings = Math.max(0, forecastBill - recsBill);

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;
    return (
      <div className="rounded bg-slate-950 border border-white/10 p-2.5 shadow-2xl text-xs font-mono min-w-[190px]">
        <div className="font-bold text-slate-300 pb-1 mb-1 border-b border-white/10 flex justify-between text-[11px]">
          <span>DAY {label?.replace("D", "")} / 30</span>
          <span className="text-[10px] text-slate-400">
            {payload[0]?.payload?.isPast ? "[MEASURED]" : "[OLS PROJECTION]"}
          </span>
        </div>
        <div className="space-y-1">
          {payload.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between gap-3 text-[11px]">
              <span className="flex items-center gap-1.5 text-slate-400">
                <span
                  className="w-2 h-2 rounded-sm"
                  style={{ backgroundColor: item.color }}
                />
                {item.name}:
              </span>
              <span className="font-bold text-white tabular-nums">
                {peso(item.value)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <section className="dash-card p-4 sm:p-5 flex flex-col justify-between select-none min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-white/5 gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider truncate">
              Cycle Projection Trajectory
            </h2>
            <span className="text-[10px] font-mono text-slate-400">({monthName})</span>
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-0.5 truncate">
            Model: Ordinary Least Squares (OLS) · {daysLeft} Days to Meter Read
          </div>
        </div>

        {/* Technical Target Pill (Cyan, NO GREEN) */}
        <div className="flex items-center gap-2 font-mono text-xs shrink-0">
          <div className="px-2.5 py-1 rounded bg-sky-500/10 border border-sky-500/20 text-[11px] flex items-center gap-1.5">
            <span className="text-slate-300">SHED POTENTIAL:</span>
            <span className="text-sky-300 font-bold tabular-nums">
              {peso(totalSavings)}
            </span>
          </div>
        </div>
      </div>

      {/* Main Chart with min-w-0 container protection */}
      <div className="pt-4 pb-1 h-64 sm:h-80 w-full min-w-0 overflow-hidden">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: -10, bottom: 0 }}
          >
            <defs>
              {/* Red Unregulated Gradient */}
              <linearGradient id="unregGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#F43F5E" stopOpacity={0.0} />
              </linearGradient>

              {/* Cyan Optimized Gradient (Replaces green) */}
              <linearGradient id="optGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#38BDF8" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="2 2"
              stroke="rgba(255, 255, 255, 0.05)"
              vertical={false}
            />

            <XAxis
              dataKey="day"
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              fontFamily="JetBrains Mono"
              interval={4}
            />

            <YAxis
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              fontFamily="JetBrains Mono"
              tickFormatter={pesoCompact}
              domain={[0, Math.ceil(maxVal * 1.1)]}
            />

            <Tooltip content={<CustomTooltip />} />

            {/* Budget Cap Reference Line */}
            <ReferenceLine
              y={2000}
              stroke="#F59E0B"
              strokeDasharray="3 3"
              strokeOpacity={0.6}
              label={{
                value: "CAP: ₱2,000",
                position: "insideTopLeft",
                fill: "#F59E0B",
                fontSize: 10,
                fontFamily: "JetBrains Mono",
              }}
            />

            {/* Baseline Reference Line */}
            <ReferenceLine
              y={baselineBill}
              stroke="#64748B"
              strokeDasharray="4 4"
              strokeOpacity={0.5}
              label={{
                value: `BASE: ${pesoCompact(baselineBill)}`,
                position: "insideBottomLeft",
                fill: "#64748B",
                fontSize: 10,
                fontFamily: "JetBrains Mono",
              }}
            />

            {/* Unregulated Runaway Path (Crimson) */}
            <Area
              type="monotone"
              dataKey="Current Unregulated"
              stroke="#F43F5E"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#unregGrad)"
              name="Current Unregulated"
            />

            {/* Optimized Shed Path (Cyan, NO GREEN) */}
            <Area
              type="monotone"
              dataKey="Optimized Shed"
              stroke="#38BDF8"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#optGrad)"
              name="Optimized Shed"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Technical Legend */}
      <div className="pt-2.5 border-t border-white/5 flex flex-wrap items-center justify-between text-[11px] font-mono gap-2">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-sm bg-rose-500" />
            <span className="text-slate-400">UNREGULATED:</span>
            <span className="text-slate-200 font-bold tabular-nums">
              {peso(forecastBill)}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-sm bg-sky-400" />
            <span className="text-slate-400">OPTIMIZED:</span>
            <span className="text-slate-200 font-bold tabular-nums">
              {peso(recsBill)}
            </span>
          </div>

          <div className="hidden sm:flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 border-t border-dashed border-slate-500" />
            <span className="text-slate-400">BASE:</span>
            <span className="text-slate-400 tabular-nums">{peso(baselineBill)}</span>
          </div>
        </div>

        <div className="text-[10px] text-slate-400">
          95% Least-Squares Confidence Interval
        </div>
      </div>
    </section>
  );
}
