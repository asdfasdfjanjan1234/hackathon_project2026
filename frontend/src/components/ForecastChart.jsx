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
import { color } from "../theme";

const AXIS = { stroke: color("line-strong"), tick: { fill: color("ink-muted"), fontSize: 11 }, tickLine: false };

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-lg bg-surface border border-line p-2.5 shadow-pop text-xs min-w-[200px]">
      <div className="font-medium text-ink pb-1.5 mb-1.5 border-b border-line flex justify-between">
        <span>{label}</span>
        <span className="text-ink-muted capitalize">{payload[0]?.payload?.status?.toLowerCase()}</span>
      </div>
      <div className="space-y-1">
        {payload.map((item, idx) => (
          <div key={idx} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-1.5 text-ink-soft">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
              {item.name}
            </span>
            <span className="font-semibold text-ink tabular-nums">{peso(item.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Cumulative bill over the billing cycle, from the backend's day-by-day forecast:
// measured days, then the projection on the current path and with the recommendations.
export default function ForecastChart({ forecast, recs, className = "" }) {
  const daily = forecast?.daily || [];
  const baselineBill = forecast?.baseline_bill ?? 0;
  const forecastBill = forecast?.forecast_bill ?? 0;
  const recsBill = forecast?.forecast_bill_with_recommendations ?? recs?.bill_with_recommendations ?? forecastBill;
  const budget = forecast?.budget;
  const cycle = forecast?.cycle;
  const coverage = forecast?.coverage;
  const projections = forecast?.projections || [];
  const weekly = (forecast?.by_model || []).some((m) => m.weekly_pattern);
  const overBudget = budget != null && forecastBill > budget;
  const pathColor = color(overBudget ? "viz-red" : "viz-blue");

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

  return (
    <section className={`dash-card p-5 flex flex-col justify-between min-w-0 ${className}`}>
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <h2 className="card-title">Cycle projection trajectory</h2>
            {cycle && (
              <span className="text-xs text-ink-muted">
                {shortDate(cycle.start)} – {shortDate(cycle.end)}
              </span>
            )}
          </div>
          <div className="card-sub mt-0.5 truncate">
            Least-squares trend{weekly ? " · weekday/weekend pattern" : ""} · {forecast?.days_left} days to meter read
          </div>
        </div>

        <span className="tech-tag tech-tag-pos tabular-nums">Savings with recs: {peso(totalSavings)}</span>
      </div>

      <div className="pt-4 pb-1 flex-1 min-h-[260px] sm:min-h-[280px] w-full min-w-0 overflow-hidden">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -6, bottom: 0 }}>
            <CartesianGrid stroke={color("line")} vertical={false} />

            <XAxis dataKey="day" {...AXIS} interval={Math.max(0, Math.ceil(chartData.length / 7) - 1)} />

            <YAxis
              {...AXIS}
              axisLine={false}
              tickFormatter={pesoCompact}
              domain={[0, Math.ceil((maxVal * 1.1) / 500) * 500]}
            />

            <Tooltip content={<CustomTooltip />} cursor={{ stroke: color("line-strong") }} />

            {budget != null && (
              <ReferenceLine
                y={budget}
                stroke={color("warn")}
                strokeDasharray="4 4"
                label={{
                  value: `Cap: ${pesoCompact(budget)}`,
                  position: "insideTopLeft",
                  fill: color("warn"),
                  fontSize: 11,
                }}
              />
            )}

            {today && (
              <ReferenceLine
                x={today}
                stroke={color("ink-muted")}
                strokeDasharray="2 4"
                label={{ value: "Today", position: "insideTopRight", fill: color("ink-muted"), fontSize: 11 }}
              />
            )}

            <Area
              type="monotone"
              dataKey="Baseline"
              stroke={color("viz-grey")}
              strokeDasharray="4 4"
              strokeWidth={1.5}
              fill="none"
              name="Without AI"
            />
            <Area
              type="monotone"
              dataKey="Current path"
              stroke={pathColor}
              strokeWidth={2}
              fill={pathColor}
              fillOpacity={0.08}
              name="Current path"
            />
            <Area
              type="monotone"
              dataKey="With recommendations"
              stroke={color("viz-green")}
              strokeWidth={2}
              fill="none"
              name="With recommendations"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="pt-3 border-t border-line flex flex-wrap items-center justify-between text-xs gap-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: pathColor }} />
            <span className="text-ink-muted">Current path:</span>
            <span className="text-ink font-bold tabular-nums">{peso(forecastBill)}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded-full bg-viz-green" />
            <span className="text-ink-muted">With recs:</span>
            <span className="text-ink font-bold tabular-nums">{peso(recsBill)}</span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5">
            <span className="w-3 border-t border-dashed border-viz-grey" />
            <span className="text-ink-muted">Without AI:</span>
            <span className="text-ink-soft font-medium tabular-nums">{peso(baselineBill)}</span>
          </div>
        </div>
        {coverage && (
          <div className="text-ink-muted">
            Based on {coverage.days_measured} measured day{coverage.days_measured === 1 ? "" : "s"}
            {coverage.hours_measured < coverage.days_measured * 20 ? ` (${coverage.hours_measured.toFixed(1)} h of readings)` : ""}
          </div>
        )}
      </div>

      {/* Projections after this cycle */}
      {projections.length > 0 && (
        <div className="mt-4 pt-4 border-t border-line grid grid-cols-3 gap-2">
          {projections.map((p) => (
            <div key={p.months} className="p-3 inset-panel min-w-0">
              <div className="text-xs text-ink-muted">
                Next {p.months === 1 ? "month" : `${p.months} months`}
              </div>
              <div className="text-base font-bold text-ink tabular-nums truncate mt-0.5">{peso(p.bill, 0)}</div>
              <div className="text-xs font-medium text-pos tabular-nums truncate">{peso(p.bill_with_recommendations, 0)} with recs</div>
              {p.months > 1 && (
                <div className="text-[11px] text-ink-muted tabular-nums truncate">≈ {peso(p.monthly_bill, 0)} / month</div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
