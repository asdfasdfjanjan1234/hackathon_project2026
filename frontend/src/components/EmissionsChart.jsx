import { useMemo, useState } from "react";
import {
  Area, Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Sparkles } from "lucide-react";
import { formatCo2, shortDate } from "../format";
import { color } from "../theme";

/**
 * AI CO₂ over the window, four ways: per day (bars), the trend (lines with a rolling average),
 * the running total against the carbon budget, and the figures as a table.
 * Device and data center keep their colours in every view; the legend switches each one off.
 */

const SERIES = [
  { key: "device", label: "This device", color: color("viz-green") },
  { key: "cloud", label: "Cloud data centers", color: color("viz-violet") },
];
const SURFACE = color("surface");
const GUIDE = color("ink-soft");
const AXIS = { tick: { fill: color("ink-muted"), fontSize: 11 }, tickLine: false, axisLine: false };
// Four even steps from 0 that reach `max`: 0, 3, 6, 9, 12 kg rather than 0, 3, 6, 11.
const STEPS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
const evenTicks = (max) => {
  const raw = max / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = STEPS.find((x) => x * mag >= raw) * mag;
  return [0, 1, 2, 3, 4].map((i) => +(i * step).toFixed(6));
};
const kgTick = (v) => (v >= 1 ? `${v.toFixed(v >= 10 ? 0 : 1)}kg` : `${Math.round(v * 1000)}g`);

const VIEWS = [
  { id: "daily", label: "Daily" },
  { id: "trend", label: "Trend" },
  { id: "total", label: "Running total" },
  { id: "table", label: "Table" },
];
const VIEW_KEY = "kilowhat-carbon-chart";

const readView = () => {
  try {
    const v = localStorage.getItem(VIEW_KEY);
    return VIEWS.some((x) => x.id === v) ? v : "daily";
  } catch {
    return "daily";
  }
};

function ChartTooltip({ active, payload, view, show, avgDays }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const cum = view === "total";
  const rows = SERIES.filter((s) => show[s.key]);
  return (
    <div className="rounded-lg bg-surface border border-line p-2.5 shadow-pop text-xs min-w-[190px]">
      <div className="font-medium text-ink pb-1.5 mb-1.5 border-b border-line">
        {cum ? `Up to ${d.day}` : d.day}
      </div>
      {rows.map((s) => (
        <div key={s.key} className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-ink-soft">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
            {s.label}
          </span>
          <span className="font-semibold text-ink tabular-nums">{formatCo2(cum ? d[`${s.key}Cum`] : d[s.key])}</span>
        </div>
      ))}
      <div className="flex justify-between gap-3 pt-1.5 mt-1.5 border-t border-line">
        <span className="text-ink-muted">{cum ? "Total so far" : "Total"}</span>
        <span className="font-semibold text-ink tabular-nums">{formatCo2(cum ? d.totalCum : d.total)}</span>
      </div>
      {view === "trend" && (
        <div className="flex justify-between gap-3">
          <span className="text-ink-muted">{avgDays}-day average</span>
          <span className="font-semibold text-ink tabular-nums">{formatCo2(d.avg)}</span>
        </div>
      )}
    </div>
  );
}

export default function EmissionsChart({ carbon, onAsk }) {
  const [view, setViewState] = useState(readView);
  const [show, setShow] = useState({ device: true, cloud: true });
  const { daily = [], window, budget, insights } = carbon;

  const setView = (v) => {
    setViewState(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      // Private mode: the choice lasts for this visit
    }
  };

  // A week's average over 30 days; a shorter one over a few days, so the line has room to move.
  const avgDays = daily.length >= 21 ? 7 : 3;

  const data = useMemo(() => {
    let device = 0;
    let cloud = 0;
    const rows = daily.map((d) => {
      const dv = show.device ? d.device_kg : 0;
      const cl = show.cloud ? d.datacenter_kg : 0;
      device += dv;
      cloud += cl;
      return {
        date: d.date, day: shortDate(d.date), device: dv, cloud: cl, total: dv + cl,
        deviceCum: device, cloudCum: cloud, totalCum: device + cloud,
      };
    });
    rows.forEach((r, i) => {
      const span = rows.slice(Math.max(0, i - avgDays + 1), i + 1);
      r.avg = span.reduce((s, x) => s + x.total, 0) / span.length;
    });
    return rows;
  }, [daily, show, avgDays]);

  const average = data.length ? data.reduce((s, d) => s + d.total, 0) / data.length : 0;
  const visible = SERIES.filter((s) => show[s.key]);
  const top = visible[visible.length - 1]?.key;
  // The cap is a month's, so it is drawn against a month of running total, not a week's.
  const budgetLine = budget && window?.id !== "7d" ? budget.kg : null;
  // Room for the budget line above the running total.
  const totalTicks =
    view === "total" && budgetLine ? evenTicks(Math.max(data.at(-1)?.totalCum ?? 0, budgetLine * 1.1)) : null;

  const toggle = (key) =>
    setShow((s) => {
      const next = { ...s, [key]: !s[key] };
      return next.device || next.cloud ? next : s; // keep at least one series on
    });

  const sub = {
    daily: `${window?.label} · kg CO₂ per day · dashed line is the daily average`,
    trend: `${window?.label} · daily CO₂ and the ${avgDays}-day average`,
    total: `CO₂ added up since ${shortDate(window?.start)}${budgetLine ? " · against your monthly budget" : ""}`,
    table: `${window?.label} · every day in the window`,
  }[view];

  const peak = insights?.peak_day;
  const question = {
    daily: peak
      ? `Explain my daily AI emissions chart. Why was ${shortDate(peak.date)} the heaviest day?`
      : "Explain my daily AI emissions chart.",
    trend: "Is my AI carbon footprint going up or down, and what is driving it?",
    total: budget ? "Will I stay under my carbon budget this cycle?" : "How much CO₂ has my AI use added up to?",
    table: "Which days had the most AI CO₂, and why?",
  }[view];

  const tooltip = (
    <Tooltip
      content={<ChartTooltip view={view} show={show} avgDays={avgDays} />}
      cursor={view === "daily" ? { fill: color("ink", 0.04) } : { stroke: color("line-strong"), strokeWidth: 1 }}
    />
  );
  const axes = (
    <>
      <CartesianGrid stroke={color("line")} vertical={false} />
      <XAxis dataKey="day" {...AXIS} minTickGap={24} />
      <YAxis
        {...AXIS}
        width={48}
        tickFormatter={kgTick}
        domain={totalTicks ? [0, totalTicks.at(-1)] : [0, "auto"]}
        ticks={totalTicks || undefined}
      />
    </>
  );

  return (
    <section className="dash-card p-5 min-w-0">
      <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-3">
        <div className="min-w-0">
          <h2 className="card-title">AI emissions over time</h2>
          <div className="card-sub mt-0.5">{sub}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onAsk && (
            <button onClick={() => onAsk(question)} className="btn" title={question}>
              <Sparkles className="w-3.5 h-3.5 text-accent" /> Ask Kilo
            </button>
          )}
          <div className="seg" role="group" aria-label="Chart view">
            {VIEWS.map((v) => (
              <button
                key={v.id}
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

      {/* Legend: also switches a series off, to see the other one on its own scale */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-3 text-xs">
        {SERIES.map((s) => (
          <button
            key={s.key}
            onClick={() => toggle(s.key)}
            aria-pressed={show[s.key]}
            title={show[s.key] ? `Hide ${s.label.toLowerCase()}` : `Show ${s.label.toLowerCase()}`}
            className={`flex items-center gap-1.5 rounded-md px-1.5 py-0.5 -mx-1.5 hover:bg-sunken ${
              show[s.key] ? "text-ink-soft" : "text-ink-muted line-through"
            }`}
          >
            <span
              className="w-2.5 h-2.5 rounded-sm border-2"
              style={{ borderColor: s.color, backgroundColor: show[s.key] ? s.color : "transparent" }}
            />
            {s.label}
          </button>
        ))}
        {view === "trend" && (
          <span className="flex items-center gap-1.5 text-ink-soft">
            <span className="w-3.5 border-t-2 border-dashed" style={{ borderColor: GUIDE }} /> {avgDays}-day average
          </span>
        )}
        {view === "total" && budgetLine && (
          <span className="flex items-center gap-1.5 text-ink-soft">
            <span className="w-3.5 border-t-2 border-dashed border-neg" /> Carbon budget
          </span>
        )}
        <span className="text-ink-muted ml-auto tabular-nums">
          Average {formatCo2(average)} a day
        </span>
      </div>

      {view === "table" ? (
        <div className="mt-3 max-h-64 overflow-y-auto rounded-lg border border-line">
          <table className="w-full text-left text-sm border-collapse whitespace-nowrap">
            <thead className="sticky top-0 bg-surface">
              <tr className="border-b border-line">
                <th className="th">Day</th>
                {visible.map((s) => (
                  <th key={s.key} className="th text-right">{s.label}</th>
                ))}
                <th className="th text-right">Total</th>
                <th className="th text-right">Running total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {[...data].reverse().map((d) => (
                <tr key={d.date} className="hover:bg-sunken">
                  <td className="py-2 px-2 text-ink-soft">{d.day}</td>
                  {visible.map((s) => (
                    <td key={s.key} className="py-2 px-2 text-right tabular-nums text-ink-soft">
                      {d[s.key] ? formatCo2(d[s.key]) : "—"}
                    </td>
                  ))}
                  <td className="py-2 px-2 text-right tabular-nums font-semibold text-ink">{d.total ? formatCo2(d.total) : "—"}</td>
                  <td className="py-2 px-2 text-right tabular-nums text-ink-muted">{formatCo2(d.totalCum)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          className="h-60 mt-3"
          role="img"
          aria-label={`AI CO₂ ${window?.label?.toLowerCase()}: ${formatCo2(data.at(-1)?.totalCum ?? 0)} in total, ${formatCo2(average)} a day on average. Choose Table for the figures.`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 8, right: 8, left: -4, bottom: 0 }}>
              {axes}
              {tooltip}
              {view === "daily" && (
                <>
                  {visible.map((s) => (
                    <Bar key={s.key} dataKey={s.key} stackId="co2" fill={s.color} stroke={SURFACE} strokeWidth={1}
                      radius={s.key === top ? [3, 3, 0, 0] : 0} isAnimationActive={false} />
                  ))}
                  {average > 0 && <ReferenceLine y={average} stroke={GUIDE} strokeDasharray="4 4" strokeWidth={1.5} />}
                </>
              )}
              {view === "trend" && (
                <>
                  {visible.map((s) => (
                    <Line key={s.key} dataKey={s.key} type="linear" stroke={s.color} strokeWidth={2} dot={false}
                      activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }} isAnimationActive={false} />
                  ))}
                  <Line dataKey="avg" type="linear" stroke={GUIDE} strokeWidth={2} strokeDasharray="5 4" dot={false}
                    activeDot={false} isAnimationActive={false} />
                </>
              )}
              {view === "total" && (
                <>
                  {visible.map((s) => (
                    <Area key={s.key} dataKey={`${s.key}Cum`} stackId="cum" type="linear" stroke={s.color} strokeWidth={2}
                      fill={s.color} fillOpacity={0.18} activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }}
                      isAnimationActive={false} />
                  ))}
                  {budgetLine && (
                    <ReferenceLine
                      y={budgetLine}
                      stroke={color("neg")}
                      strokeDasharray="4 4"
                      strokeWidth={1.5}
                      label={{ value: `Budget ${budgetLine} kg`, position: "insideTopLeft", fill: color("ink-soft"), fontSize: 11 }}
                    />
                  )}
                </>
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
