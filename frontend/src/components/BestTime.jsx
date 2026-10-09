import { useMemo } from "react";
import { BarChart, Bar, Cell, LabelList, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { CalendarClock, SlidersHorizontal } from "lucide-react";
import { peso } from "../format";
import { color } from "../theme";

// Highlight-vs-context: the best window in green, the rest of off-peak in blue, peak hours
// recede in grey. The best window is also labelled, since green and blue are close under tritanopia.
const BEST = color("viz-green");
const OFFPEAK = color("viz-blue");
const PEAK = color("viz-grey", 0.55);
const SURFACE = color("surface");
const AXIS = { tick: { fill: color("ink-muted"), fontSize: 11 }, tickLine: false, axisLine: false };

const hourLabel = (h) => `${h % 12 || 12}${h < 12 ? "a" : "p"}`;
const inWindow = (h, w) =>
  w && w.g_per_kwh != null && (h - w.start_hour + 24) % 24 < (w.end_hour - w.start_hour + 24) % 24;

function HourTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg bg-surface border border-line p-2 shadow-pop text-xs">
      <div className="text-ink-soft font-medium">
        {d.label} · {d.peak ? "peak" : "off-peak"}
        {d.best && <span className="text-pos"> · best</span>}
      </div>
      <div className="text-ink font-semibold tabular-nums">{peso(d.rate)} / kWh</div>
    </div>
  );
}

function Tile({ title, value, sub, accent = "text-ink", highlight }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "border-pos/30 bg-pos/[0.06]" : "border-line bg-sunken"}`}>
      <div className={`text-xs font-medium ${highlight ? "text-pos" : "text-ink-muted"}`}>{title}</div>
      <div className={`text-base font-bold mt-0.5 tabular-nums ${accent}`}>{value}</div>
      <div className="text-xs text-ink-muted leading-snug mt-0.5">{sub}</div>
    </div>
  );
}

export default function BestTime({ info, onOpenSettings }) {
  const pop = info?.tariff === "pop";
  const best = info?.best;
  // On a flat rate the chart shows what POP would charge, so the cheap hours are still visible.
  const data = useMemo(
    () =>
      (info?.schedule || []).map((s) => ({
        hour: s.hour,
        label: `${s.hour % 12 || 12}:00 ${s.hour < 12 ? "AM" : "PM"}`,
        peak: s.peak,
        rate: pop ? s.rate : s.peak ? info.peak_rate : info.offpeak_rate,
        best: inWindow(s.hour, best),
      })),
    [info, pop, best]
  );
  if (!info) return null;
  const firstBest = data.find((d) => d.best)?.hour;
  const shift = info.shift;
  const whatIf = info.what_if_pop;

  return (
    <section className="dash-card p-5 min-w-0">
      <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-2">
        <div className="min-w-0">
          <h2 className="card-title flex items-center gap-2">
            <CalendarClock className="w-4 h-4 text-ink-muted" /> Best time to run local AI
          </h2>
          <div className="card-sub mt-0.5">
            When batch jobs (evals, indexing, long agent runs) cost least on your tariff and the grid is cleanest
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="tech-tag tech-tag-neutral tabular-nums">
            {pop
              ? `Now: ${info.now.peak ? "peak" : "off-peak"} ${peso(info.now.rate)}/kWh · ${
                  info.now.peak ? "off-peak" : "peak"
                } from ${info.now.changes_at}`
              : `Same rate all day: ${peso(info.rate)}/kWh`}
          </span>
          <button onClick={onOpenSettings} title="Change tariff" aria-label="Change tariff" className="btn-icon">
            <SlidersHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
        <Tile
          highlight
          title="Best time for batch jobs"
          value={best ? best.label : "Any hour"}
          sub={best ? best.reason : "Same price every hour. Connect hourly grid data to find the cleanest hours."}
        />
        <Tile
          title="Cheapest hours"
          value={pop ? `Off-peak ${peso(info.offpeak_rate)}/kWh` : "Any hour"}
          sub={pop ? info.offpeak_label : "Your rate is the same at every hour, so timing doesn't change the bill."}
        />
        {pop ? (
          <Tile
            title="Shift batch jobs off-peak"
            value={shift ? `-${peso(shift.savings)} / mo` : "Already off-peak"}
            accent="text-pos"
            sub={
              shift
                ? `${Math.round(info.ai.peak_share * 100)}% of your AI energy is in peak hours; moving ${Math.round(
                    shift.share * 100
                  )}% of it`
                : info.ai.kwh_month
                ? "Your AI already runs in off-peak hours"
                : "No AI use measured yet"
            }
          />
        ) : (
          <Tile
            title="On Meralco Peak/Off-Peak"
            value={
              whatIf.cost_month_flat
                ? `${peso(whatIf.cost_month_pop_shifted)} vs ${peso(whatIf.cost_month_flat)} / mo`
                : "No AI use measured yet"
            }
            sub={
              `AI cost with batch jobs moved off-peak, vs now. ` +
              (whatIf.eligible
                ? `Your bill suggests ~${whatIf.household_kwh_month} kWh a month, enough to join (${whatIf.min_kwh} kWh minimum).`
                : `POP needs an average of ${whatIf.min_kwh} kWh a month; your bill suggests ~${whatIf.household_kwh_month}.`)
            }
          />
        )}
      </div>

      <div className="mt-4">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted mb-2">
          <span>{pop ? "Your rate today · ₱ / kWh" : "If you were on Meralco POP · ₱ / kWh today"}</span>
          <span className="flex items-center gap-3">
            {best?.g_per_kwh != null && (
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: BEST }} /> Best window
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: OFFPEAK }} /> Off-peak
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: PEAK }} /> Peak
            </span>
          </span>
        </div>
        <div className="h-36">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 16, right: 4, left: -16, bottom: 0 }}>
              <CartesianGrid stroke={color("line")} vertical={false} />
              <XAxis dataKey="hour" {...AXIS} interval={2} tickFormatter={hourLabel} />
              <YAxis {...AXIS} domain={[0, "auto"]} />
              <Tooltip content={<HourTooltip />} cursor={{ fill: color("ink", 0.04) }} />
              <Bar dataKey="rate" radius={[3, 3, 0, 0]} stroke={SURFACE} strokeWidth={2}>
                {data.map((d) => (
                  <Cell key={d.hour} fill={d.best ? BEST : d.peak ? PEAK : OFFPEAK} />
                ))}
                <LabelList
                  dataKey="hour"
                  content={({ x, y, value }) =>
                    value === firstBest ? (
                      <text x={x} y={y - 5} textAnchor="start" fontSize={11} fontWeight={600} fill={BEST}>
                        Best
                      </text>
                    ) : null
                  }
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <p className="mt-3 text-xs text-ink-muted leading-relaxed">
        Philippine households have no live hourly price: WESM spot prices reach the bill only as a monthly
        average. Peak/off-peak times are Meralco's POP schedule; holidays aren't included.
      </p>
    </section>
  );
}
