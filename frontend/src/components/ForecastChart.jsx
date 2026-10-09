import { useMemo, useState } from "react";
import {
  ComposedChart,
  Area,
  Bar,
  Cell,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceDot,
} from "recharts";
import { formatKwh, peso, pesoCompact, shortDate } from "../format";
import { color } from "../theme";

const AXIS = { stroke: color("line-strong"), tick: { fill: color("ink-muted"), fontSize: 11 }, tickLine: false };

// AI cost is the part of the bill the forecast moves; on the whole bill it's a few pesos on top of the
// baseline and the lines sit on top of each other. Per day shows what the model expects each day.
const VIEWS = [
  { id: "ai", label: "AI cost" },
  { id: "daily", label: "Per day" },
  { id: "total", label: "Total bill" },
];
const VIEW_KEY = "watttrace-forecast-chart";

const readView = () => {
  try {
    const v = localStorage.getItem(VIEW_KEY);
    return VIEWS.some((x) => x.id === v) ? v : "ai";
  } catch {
    return "ai";
  }
};

// Peso ticks with centavos when the scale is small (AI cost per day is often under ₱1).
const pesoTick = (max) => (n) => (max < 5 ? peso(n, max < 1 ? 2 : 1) : pesoCompact(n));

function Row({ swatch, label, value, muted }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-1.5 text-ink-soft">
        {swatch}
        {label}
      </span>
      <span className={`tabular-nums ${muted ? "text-ink-muted" : "font-semibold text-ink"}`}>{value}</span>
    </div>
  );
}

const Stroke = ({ c, dashed }) => (
  <span className={`w-3 border-t-2 ${dashed ? "border-dashed" : ""}`} style={{ borderColor: c }} />
);
const Swatch = ({ c, opacity = 1 }) => (
  <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: c, opacity }} />
);

function ChartTooltip({ active, payload, view, pathColor, methodName }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const ahead = d.status === "PROJECTED" || d.status === "TODAY";
  const status = { TODAY: "Today", MEASURED: "Measured", ESTIMATED: "Estimated", PROJECTED: `Forecast · ${methodName}` }[d.status];
  return (
    <div className="rounded-lg bg-surface border border-line p-2.5 shadow-pop text-xs min-w-[210px]">
      <div className="font-medium text-ink pb-1.5 mb-1.5 border-b border-line flex justify-between gap-3">
        <span>{view === "daily" ? d.day : `Up to ${d.day}`}</span>
        <span className="text-ink-muted">{status}</span>
      </div>
      <div className="space-y-1">
        {view === "daily" ? (
          <>
            <Row swatch={<Swatch c={pathColor} opacity={ahead ? 0.45 : 1} />} label="AI cost" value={peso(d.dayCost)} />
            <Row label="AI energy" value={formatKwh(d.dayKwh)} muted />
          </>
        ) : (
          <>
            <Row
              swatch={<Stroke c={pathColor} dashed={d.status === "PROJECTED"} />}
              label={view === "total" ? "Bill" : "AI cost"}
              value={peso(d.value)}
            />
            {d.band && d.status === "PROJECTED" && (
              <Row label="80% range" value={`${peso(d.band[0])} – ${peso(d.band[1])}`} muted />
            )}
            {d.recs != null && d.status === "PROJECTED" && (
              <Row swatch={<Stroke c={color("viz-green")} dashed />} label="With recommendations" value={peso(d.recs)} />
            )}
            {view === "total" && <Row swatch={<Stroke c={color("viz-grey")} dashed />} label="Without AI" value={peso(d.baseline)} muted />}
          </>
        )}
      </div>
    </div>
  );
}

// The billing cycle from the backend's day-by-day forecast: measured days as a solid line, the projection
// (the device's fine-tuned ARIMA when the backend uses it, forecast.method, else the trend) dashed after
// today with its 80% range shaded, and the path with the recommendations.
export default function ForecastChart({ forecast, recs, className = "" }) {
  const [view, setViewState] = useState(readView);
  const setView = (v) => {
    setViewState(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* the view just isn't remembered */
    }
  };

  const daily = forecast?.daily || [];
  const baselineBill = forecast?.baseline_bill ?? 0;
  const forecastBill = forecast?.forecast_bill ?? 0;
  const recsBill = forecast?.forecast_bill_with_recommendations ?? recs?.bill_with_recommendations ?? forecastBill;
  const budget = forecast?.budget;
  const cycle = forecast?.cycle;
  const coverage = forecast?.coverage;
  const projections = forecast?.projections || [];
  const weekly = (forecast?.by_model || []).some((m) => m.weekly_pattern);
  const method = forecast?.method;
  const methodName = method?.name === "arima" ? "ARIMA" : "trend";
  const range = forecast?.forecast_range;
  const overBudget = budget != null && forecastBill > budget;
  const pathColor = color(overBudget ? "viz-red" : "viz-blue");
  const totalSavings = Math.max(0, forecastBill - recsBill);
  const total = view === "total";

  const chartData = useMemo(() => {
    const rows = daily.map((d) => ({
      day: shortDate(d.date),
      status: d.is_today ? "TODAY" : d.is_past ? (d.measured ? "MEASURED" : "ESTIMATED") : "PROJECTED",
      ahead: !d.is_past,
      baseline: d.baseline_to_date,
      // The AI part of the bill so far, or the whole bill
      value: d.bill_to_date - (total ? 0 : d.baseline_to_date),
      recsValue: d.bill_to_date_with_recommendations - (total ? 0 : d.baseline_to_date),
      offset: total ? d.baseline_to_date : 0,
      dayCost: d.ai_cost,
      dayKwh: d.ai_kwh,
    }));

    // The backend gives the range of the cycle's total. Spread it over the days ahead in proportion to
    // how much is still to come by each of them, from today's value to the range at the end.
    const anchor = rows.find((r) => r.status === "TODAY");
    const last = rows[rows.length - 1];
    const toCome = last && anchor ? last.value - anchor.value : 0;
    const showRecs = rows.some((r) => Math.abs(r.recsValue - r.value) >= 0.005);
    return rows.map((r) => {
      const out = { ...r, measured: r.ahead && r.status !== "TODAY" ? null : r.value, projected: r.ahead ? r.value : null };
      out.recs = showRecs && r.ahead ? r.recsValue : null;
      if (range && anchor && toCome > 0 && r.ahead) {
        const share = (r.value - anchor.value) / toCome;
        const end = (bill) => bill - (total ? 0 : baselineBill) - last.value; // the range's ends, from the line's end
        out.band = [r.value + share * end(range.low), r.value + share * end(range.high)];
      }
      return out;
    });
  }, [daily, total, range, baselineBill]);

  const today = chartData.find((d) => d.status === "TODAY")?.day;
  const last = chartData[chartData.length - 1];
  const aiForecast = forecastBill - baselineBill;
  const aiRecs = recsBill - baselineBill;
  const daysAhead = chartData.filter((d) => d.status === "PROJECTED");
  const perDayAhead = daysAhead.length ? daysAhead.reduce((s, d) => s + d.dayCost, 0) / daysAhead.length : null;

  const maxVal =
    view === "daily"
      ? Math.max(...chartData.map((d) => d.dayCost), 0.01)
      : total
        ? Math.max(forecastBill, budget || 0, range?.high || 0, 1)
        : Math.max(last?.value || 0, last?.band?.[1] || 0, 0.01);
  const tick = pesoTick(maxVal);
  // The whole bill on round ₱500 (or ₱1,000) steps
  const totalMax = Math.ceil((maxVal * 1.1) / 500) * 500;
  const totalStep = totalMax <= 3000 ? 500 : 1000;
  const totalTicks = Array.from({ length: Math.ceil(totalMax / totalStep) + 1 }, (_, i) => i * totalStep);

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
          <div className="card-sub mt-0.5 truncate" title={method?.reason}>
            {method?.name === "arima"
              ? "ARIMA fine-tuned on this device"
              : `Least-squares trend${weekly ? " · weekday/weekend pattern" : ""}`}{" "}
            · {forecast?.days_left} days to meter read
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="tech-tag tech-tag-pos tabular-nums">Savings with recs: {peso(totalSavings)}</span>
          <div className="seg" role="group" aria-label="Chart view">
            {VIEWS.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => setView(v.id)}
                className={`seg-item ${view === v.id ? "seg-item-active" : ""}`}
                aria-pressed={view === v.id}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="pt-4 pb-1 flex-1 min-h-[260px] sm:min-h-[280px] w-full min-w-0 overflow-hidden">
        {/* minHeight keeps the chart visible when the card isn't stretched to a fixed height (Billing Projection view). */}
        <ResponsiveContainer width="100%" height="100%" minHeight={260}>
          <ComposedChart data={chartData} margin={{ top: 16, right: view === "daily" ? 16 : 44, left: 0, bottom: 0 }} barCategoryGap={2}>
            <CartesianGrid stroke={color("line")} vertical={false} />

            <XAxis dataKey="day" {...AXIS} interval={Math.max(0, Math.ceil(chartData.length / 7) - 1)} />

            <YAxis
              {...AXIS}
              axisLine={false}
              width={52}
              tickFormatter={tick}
              domain={total ? [0, totalTicks[totalTicks.length - 1]] : [0, "auto"]}
              ticks={total ? totalTicks : undefined}
            />

            <Tooltip
              content={<ChartTooltip view={view} pathColor={pathColor} methodName={methodName} />}
              cursor={view === "daily" ? { fill: color("ink", 0.04) } : { stroke: color("line-strong") }}
            />

            {total && budget != null && (
              <ReferenceLine
                y={budget}
                stroke={color("warn")}
                strokeDasharray="4 4"
                label={{ value: `Cap: ${pesoCompact(budget)}`, position: "insideTopLeft", fill: color("ink-muted"), fontSize: 11 }}
              />
            )}

            {today && (
              <ReferenceLine
                x={today}
                stroke={color("ink-muted")}
                strokeDasharray="2 4"
                label={{ value: "Today", position: "top", fill: color("ink-muted"), fontSize: 11 }}
              />
            )}

            {view === "daily" ? (
              <Bar dataKey="dayCost" name="AI cost" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={pathColor} fillOpacity={d.ahead ? 0.45 : 1} />
                ))}
              </Bar>
            ) : (
              <>
                {/* 80% range of the projection */}
                <Area
                  dataKey="band"
                  stroke="none"
                  fill={pathColor}
                  fillOpacity={0.12}
                  connectNulls={false}
                  isAnimationActive={false}
                  activeDot={false}
                />
                {total && (
                  <Line
                    dataKey="baseline"
                    stroke={color("viz-grey")}
                    strokeDasharray="4 4"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={false}
                    isAnimationActive={false}
                  />
                )}
                <Line dataKey="recs" stroke={color("viz-green")} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                <Line dataKey="measured" stroke={pathColor} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="projected" stroke={pathColor} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                {last && (
                  <ReferenceDot
                    x={last.day}
                    y={last.value}
                    r={4}
                    fill={pathColor}
                    stroke={color("surface")}
                    strokeWidth={2}
                    label={{ value: peso(last.value), position: "top", fill: color("ink"), fontSize: 11, fontWeight: 600 }}
                  />
                )}
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="pt-3 border-t border-line flex flex-wrap items-center justify-between text-xs gap-2">
        {view === "daily" ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <div className="flex items-center gap-1.5">
              <Swatch c={pathColor} />
              <span className="text-ink-muted">Measured</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Swatch c={pathColor} opacity={0.45} />
              <span className="text-ink-muted">Forecast ({methodName}):</span>
              {perDayAhead != null && <span className="text-ink font-bold tabular-nums">≈ {peso(perDayAhead)} / day</span>}
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <div className="flex items-center gap-1.5">
              <Stroke c={pathColor} />
              <span className="text-ink-muted">Measured</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Stroke c={pathColor} dashed />
              <span className="text-ink-muted">{total ? "Bill" : "AI cost"} ({methodName}):</span>
              <span className="text-ink font-bold tabular-nums">{peso(total ? forecastBill : aiForecast)}</span>
              {range && (
                <span className="text-ink-muted tabular-nums" title={`${Math.round((method?.interval ?? 0.8) * 100)}% range`}>
                  ({peso(range.low - (total ? 0 : baselineBill))} – {peso(range.high - (total ? 0 : baselineBill))})
                </span>
              )}
            </div>
            {range && (
              <div className="hidden sm:flex items-center gap-1.5">
                <Swatch c={pathColor} opacity={0.2} />
                <span className="text-ink-muted">{Math.round((method?.interval ?? 0.8) * 100)}% range</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <Stroke c={color("viz-green")} dashed />
              <span className="text-ink-muted">With recs:</span>
              <span className="text-ink font-bold tabular-nums">{peso(total ? recsBill : aiRecs)}</span>
            </div>
            {total && (
              <div className="hidden sm:flex items-center gap-1.5">
                <Stroke c={color("viz-grey")} dashed />
                <span className="text-ink-muted">Without AI:</span>
                <span className="text-ink-soft font-medium tabular-nums">{peso(baselineBill)}</span>
              </div>
            )}
          </div>
        )}
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
