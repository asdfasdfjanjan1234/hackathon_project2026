import { useMemo } from "react";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Clock, PlugZap } from "lucide-react";
import { formatCo2, formatWh } from "../format";

// Highlight-vs-context (dataviz validator, dark surface #121927): the cleanest window in
// emerald, other hours recede in slate; your use is one series in sky.
const CLEAN = "#059669";
const CONTEXT = "#3B4A61";
const USE = "#0284C7";
const SURFACE = "#121927";

const hourLabel = (h) => `${h % 12 || 12}${h < 12 ? "a" : "p"}`;
const inWindow = (h, w) => w && (h - w.start_hour + 24) % 24 < (w.end_hour - w.start_hour + 24) % 24;

function HourTooltip({ active, payload, format }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded bg-slate-950 border border-white/10 p-2 shadow-2xl text-[11px] font-mono">
      <div className="text-slate-300 font-bold">
        {d.label}
        {d.clean && <span className="text-emerald-300"> · cleanest</span>}
      </div>
      <div className="text-white tabular-nums">{format(payload[0].value)}</div>
    </div>
  );
}

// Recharts only recognizes its own axis elements, so the shared hour axis is a set of props.
const HOUR_AXIS = {
  dataKey: "hour",
  stroke: "#64748B",
  fontSize: 10,
  tickLine: false,
  axisLine: false,
  interval: 2,
  tickFormatter: hourLabel,
};

export default function CleanHours({ info }) {
  const plan = info?.plan;
  const data = useMemo(
    () =>
      Array.from({ length: 24 }, (_, h) => ({
        hour: h,
        label: `${h % 12 || 12}:00 ${h < 12 ? "AM" : "PM"}`,
        g: info?.intensity?.[h]?.g_per_kwh ?? null,
        wh: (info?.use?.[h]?.kwh_per_day ?? 0) * 1000,
        clean: inWindow(h, plan?.cleanest),
      })),
    [info, plan]
  );
  if (!info) return null;
  const hasGrid = data.some((d) => d.g != null);
  const hasUse = data.some((d) => d.wh > 0);

  return (
    <section className="dash-card p-4 sm:p-5 min-w-0">
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-white/5 gap-2">
        <div className="min-w-0">
          <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-emerald-400" /> Cleanest Hours to Run AI
          </h2>
          <div className="text-[10px] text-slate-400">
            Grid carbon intensity by hour ({info.zone}
            {info.source === "forecast" ? ", next 24 h forecast" : info.source === "history" ? ", last 24 h" : ""}) and
            when this device runs AI
          </div>
        </div>
        {info.now && (
          <span className="tech-tag tech-tag-neutral">GRID NOW: {Math.round(info.now.g_per_kwh)} g CO₂/kWh</span>
        )}
      </div>

      {plan && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3 font-mono">
          <div className="p-2.5 rounded bg-white/[0.02] border border-emerald-500/20">
            <div className="text-[10px] text-emerald-300 uppercase font-semibold">Cleanest {plan.window_hours} h</div>
            <div className="text-sm font-bold text-white">{plan.cleanest.label}</div>
            <div className="text-[10px] text-slate-400">{Math.round(plan.cleanest.g_per_kwh)} g CO₂/kWh</div>
          </div>
          <div className="p-2.5 rounded bg-white/[0.02] border border-white/5">
            <div className="text-[10px] text-slate-400 uppercase font-semibold">Your AI hours</div>
            <div className="text-sm font-bold text-white">
              {plan.peak_use_label ? `Peak ${plan.peak_use_label}` : "No AI use yet"}
            </div>
            <div className="text-[10px] text-slate-400">
              {plan.weighted_g_per_kwh != null ? `${Math.round(plan.weighted_g_per_kwh)} g CO₂/kWh on average` : "—"}
            </div>
          </div>
          <div className="p-2.5 rounded bg-white/[0.02] border border-white/5">
            <div className="text-[10px] text-slate-400 uppercase font-semibold">Shift batch jobs</div>
            <div className="text-sm font-bold text-emerald-300">
              {plan.shift ? `-${formatCo2(plan.shift.co2_saved_kg)} / mo` : "Already clean"}
            </div>
            <div className="text-[10px] text-slate-400">
              {plan.shift ? `${Math.round(plan.shift.share * 100)}% of AI energy moved · bill unchanged` : "Your AI runs in clean hours"}
            </div>
          </div>
        </div>
      )}

      {hasGrid ? (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
            <span>GRID g CO₂ / kWh</span>
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: CLEAN }} /> Cleanest window
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: CONTEXT }} /> Other hours
              </span>
            </span>
          </div>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis {...HOUR_AXIS} />
                <YAxis stroke="#64748B" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip
                  content={<HourTooltip format={(v) => (v == null ? "no data" : `${Math.round(v)} g CO₂/kWh`)} />}
                  cursor={{ fill: "rgba(255,255,255,0.04)" }}
                />
                <Bar dataKey="g" radius={[4, 4, 0, 0]} stroke={SURFACE} strokeWidth={2}>
                  {data.map((d) => (
                    <Cell key={d.hour} fill={d.clean ? CLEAN : CONTEXT} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="mt-3 p-3 rounded border border-amber-500/25 bg-amber-500/5 text-[11px] text-slate-300 flex gap-2.5">
          <PlugZap className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-mono font-bold text-amber-300 uppercase text-[10px]">Hourly grid data not connected</div>
            <p>
              The DOE grid factor is one number for the whole year, so it can't tell clean hours from dirty ones.
              Get a free personal token at app.electricitymaps.com, then add{" "}
              <code className="text-sky-300">ELECTRICITYMAPS_TOKEN=…</code> to <code className="text-sky-300">backend/.env</code>{" "}
              and restart the backend.
            </p>
            {info.configured && info.error && <p className="text-rose-300">Electricity Maps: {info.error}</p>}
          </div>
        </div>
      )}

      <div className="mt-3">
        <div className="text-[10px] font-mono text-slate-400 mb-1">YOUR AI ENERGY BY HOUR · Wh per day, last 30 days</div>
        {hasUse ? (
          <div className="h-28">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis {...HOUR_AXIS} />
                <YAxis stroke="#64748B" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip content={<HourTooltip format={(v) => `${formatWh(v)} a day`} />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Bar dataKey="wh" fill={USE} radius={[4, 4, 0, 0]} stroke={SURFACE} strokeWidth={2} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="p-4 text-center text-xs text-slate-400">No AI use measured on this device yet.</div>
        )}
      </div>
    </section>
  );
}
