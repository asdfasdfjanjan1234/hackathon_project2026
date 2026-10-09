import { useMemo } from "react";
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
import { peso, pesoCompact, shortDate } from "../format";

// Cumulative bill over the billing cycle, from the backend's day-by-day forecast:
// measured days, then the projection on the current path and with the recommendations.
export default function ForecastChart({ forecast }) {
  const daily = forecast?.daily || [];
  const baselineBill = forecast?.baseline_bill ?? 0;
  const forecastBill = forecast?.forecast_bill ?? 0;
  const recsBill = forecast?.forecast_bill_with_recommendations ?? forecastBill;
  const budget = forecast?.budget;
  const cycle = forecast?.cycle;
  const coverage = forecast?.coverage;
  const projections = forecast?.projections || [];
  const weekly = (forecast?.by_model || []).some((m) => m.weekly_pattern);

  const chartData = useMemo(
    () =>
      daily.map((d) => ({
        day: shortDate(d.date),
        date: d.date,
        status: d.is_today ? "TODAY" : d.is_past ? (d.measured ? "MEASURED" : "ESTIMATED") : "PROJECTED",
        Baseline: d.baseline_to_date,
        "Current path": d.bill_to_date,
        "With recommendations": d.bill_to_date_with_recommendations,
      })),
    [daily]
  );
  const today = chartData.find((d) => d.status === "TODAY")?.day;

  const maxVal = Math.max(forecastBill, budget || 0, 1);
  const totalSavings = Math.max(0, forecastBill - recsBill);

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;
    return (
      <div className="rounded bg-slate-950 border border-white/10 p-2.5 shadow-2xl text-xs font-mono min-w-[200px]">
        <div className="font-bold text-slate-300 pb-1 mb-1 border-b border-white/10 flex justify-between text-[11px]">
          <span>{label}</span>
          <span className="text-[10px] text-slate-400">[{payload[0]?.payload?.status}]</span>
        </div>
        <div className="space-y-1">
          {payload.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between gap-3 text-[11px]">
              <span className="flex items-center gap-1.5 text-slate-400">
                <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: item.color }} />
                {item.name}:
              </span>
              <span className="font-bold text-white tabular-nums">{peso(item.value)}</span>
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
            {cycle && (
              <span className="text-[10px] font-mono text-slate-400">
                ({shortDate(cycle.start)} – {shortDate(cycle.end)})
              </span>
            )}
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-0.5 truncate">
            Least-squares trend{weekly ? " · weekday/weekend pattern" : ""} · {forecast?.days_left} days to meter read
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs shrink-0">
          <div className="px-2.5 py-1 rounded bg-sky-500/10 border border-sky-500/20 text-[11px] flex items-center gap-1.5">
            <span className="text-slate-300">SAVED THIS CYCLE:</span>
            <span className="text-sky-300 font-bold tabular-nums">{peso(totalSavings)}</span>
          </div>
        </div>
      </div>

      <div className="pt-4 pb-1 h-64 sm:h-80 w-full min-w-0 overflow-hidden">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="unregGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#F43F5E" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="optGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#38BDF8" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="2 2" stroke="rgba(255, 255, 255, 0.05)" vertical={false} />

            <XAxis
              dataKey="day"
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              fontFamily="JetBrains Mono"
              interval={Math.max(0, Math.ceil(chartData.length / 7) - 1)}
            />

            <YAxis
              stroke="#64748B"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              fontFamily="JetBrains Mono"
              tickFormatter={pesoCompact}
              domain={[0, Math.ceil((maxVal * 1.1) / 500) * 500]}
            />

            <Tooltip content={<CustomTooltip />} />

            {budget != null && (
              <ReferenceLine
                y={budget}
                stroke="#F59E0B"
                strokeDasharray="3 3"
                strokeOpacity={0.6}
                label={{
                  value: `CAP: ${pesoCompact(budget)}`,
                  position: "insideTopLeft",
                  fill: "#F59E0B",
                  fontSize: 10,
                  fontFamily: "JetBrains Mono",
                }}
              />
            )}

            {today && (
              <ReferenceLine
                x={today}
                stroke="#94A3B8"
                strokeDasharray="2 4"
                strokeOpacity={0.6}
                label={{ value: "TODAY", position: "insideTopRight", fill: "#94A3B8", fontSize: 9, fontFamily: "JetBrains Mono" }}
              />
            )}

            <Area
              type="monotone"
              dataKey="Baseline"
              stroke="#64748B"
              strokeDasharray="4 4"
              strokeWidth={1}
              fill="none"
              name="Without AI"
            />
            <Area
              type="monotone"
              dataKey="Current path"
              stroke="#F43F5E"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#unregGrad)"
              name="Current path"
            />
            <Area
              type="monotone"
              dataKey="With recommendations"
              stroke="#38BDF8"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#optGrad)"
              name="With recommendations"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="pt-2.5 border-t border-white/5 flex flex-wrap items-center justify-between text-[11px] font-mono gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-sm bg-rose-500" />
            <span className="text-slate-400">CURRENT PATH:</span>
            <span className="text-slate-200 font-bold tabular-nums">{peso(forecastBill)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-1 rounded-sm bg-sky-400" />
            <span className="text-slate-400">WITH RECS:</span>
            <span className="text-slate-200 font-bold tabular-nums">{peso(recsBill)}</span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 border-t border-dashed border-slate-500" />
            <span className="text-slate-400">WITHOUT AI:</span>
            <span className="text-slate-400 tabular-nums">{peso(baselineBill)}</span>
          </div>
        </div>
        {coverage && (
          <div className="text-[10px] text-slate-400">
            Based on {coverage.days_measured} measured day{coverage.days_measured === 1 ? "" : "s"}
            {coverage.hours_measured < coverage.days_measured * 20 ? ` (${coverage.hours_measured.toFixed(1)} h of readings)` : ""}
          </div>
        )}
      </div>

      {/* Projections after this cycle */}
      {projections.length > 0 && (
        <div className="mt-3 pt-3 border-t border-white/5 grid grid-cols-3 gap-2 font-mono">
          {projections.map((p) => (
            <div key={p.months} className="p-2 rounded bg-black/30 border border-white/5 min-w-0">
              <div className="text-[9px] uppercase tracking-wider text-slate-400">
                Next {p.months === 1 ? "month" : `${p.months} months`}
              </div>
              <div className="text-sm font-bold text-rose-300 tabular-nums truncate">{peso(p.bill, 0)}</div>
              <div className="text-[10px] text-sky-300 tabular-nums truncate">{peso(p.bill_with_recommendations, 0)} with recs</div>
              {p.months > 1 && (
                <div className="text-[9px] text-slate-500 tabular-nums truncate">≈ {peso(p.monthly_bill, 0)} / month</div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
