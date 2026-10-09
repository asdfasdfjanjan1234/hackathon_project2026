import { useMemo } from "react";
import { BarChart, Bar, Cell, LabelList, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { CalendarClock, SlidersHorizontal } from "lucide-react";
import { peso } from "../format";

// Highlight-vs-context (dataviz validator, dark surface #121927): the best window in emerald,
// the rest of off-peak in sky, peak hours recede in slate. The best window is also labelled,
// since emerald and sky are close under tritanopia.
const BEST = "#059669";
const OFFPEAK = "#0284C7";
const PEAK = "#3B4A61";
const SURFACE = "#121927";

const hourLabel = (h) => `${h % 12 || 12}${h < 12 ? "a" : "p"}`;
const inWindow = (h, w) =>
  w && w.g_per_kwh != null && (h - w.start_hour + 24) % 24 < (w.end_hour - w.start_hour + 24) % 24;

function HourTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded bg-slate-950 border border-white/10 p-2 shadow-2xl text-[11px] font-mono">
      <div className="text-slate-300 font-bold">
        {d.label} · {d.peak ? "peak" : "off-peak"}
        {d.best && <span className="text-emerald-300"> · best</span>}
      </div>
      <div className="text-white tabular-nums">{peso(d.rate)} / kWh</div>
    </div>
  );
}

function Tile({ title, value, sub, accent = "text-white", highlight }) {
  return (
    <div className={`p-2.5 rounded bg-white/[0.02] border ${highlight ? "border-emerald-500/20" : "border-white/5"}`}>
      <div className={`text-[10px] uppercase font-semibold ${highlight ? "text-emerald-300" : "text-slate-400"}`}>{title}</div>
      <div className={`text-sm font-bold ${accent}`}>{value}</div>
      <div className="text-[10px] text-slate-400 font-sans leading-snug">{sub}</div>
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
    <section className="dash-card p-4 sm:p-5 min-w-0">
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-white/5 gap-2">
        <div className="min-w-0">
          <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <CalendarClock className="w-3.5 h-3.5 text-emerald-400" /> Best Time to Run Local AI
          </h2>
          <div className="text-[10px] text-slate-400">
            When batch jobs (evals, indexing, long agent runs) cost least on your tariff and the grid is cleanest
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="tech-tag tech-tag-neutral">
            {pop
              ? `NOW: ${info.now.peak ? "PEAK" : "OFF-PEAK"} ${peso(info.now.rate)}/kWh · ${
                  info.now.peak ? "OFF-PEAK" : "PEAK"
                } FROM ${info.now.changes_at}`
              : `SAME RATE ALL DAY: ${peso(info.rate)}/kWh`}
          </span>
          <button
            onClick={onOpenSettings}
            title="Change tariff"
            className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-white/[0.04]"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3 font-mono">
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
            accent="text-emerald-300"
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

      <div className="mt-3">
        <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-slate-400 mb-1">
          <span>{pop ? "YOUR RATE TODAY · ₱ / kWh" : "IF YOU WERE ON MERALCO POP · ₱ / kWh TODAY"}</span>
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
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 14, right: 4, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="2 2" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="hour" stroke="#64748B" fontSize={10} tickLine={false} axisLine={false} interval={2}
                     tickFormatter={hourLabel} />
              <YAxis stroke="#64748B" fontSize={10} tickLine={false} axisLine={false} domain={[0, "auto"]} />
              <Tooltip content={<HourTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="rate" radius={[4, 4, 0, 0]} stroke={SURFACE} strokeWidth={2}>
                {data.map((d) => (
                  <Cell key={d.hour} fill={d.best ? BEST : d.peak ? PEAK : OFFPEAK} />
                ))}
                <LabelList
                  dataKey="hour"
                  content={({ x, y, value }) =>
                    value === firstBest ? (
                      <text x={x} y={y - 4} textAnchor="start" fontSize={9} fill="#6EE7B7"
                            fontFamily="monospace">
                        BEST
                      </text>
                    ) : null
                  }
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <p className="mt-2 text-[10px] text-slate-500 font-sans">
        Philippine households have no live hourly price: WESM spot prices reach the bill only as a monthly
        average. Peak/off-peak times are Meralco's POP schedule; holidays aren't included.
      </p>
    </section>
  );
}
