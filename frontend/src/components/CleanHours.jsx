import { useMemo } from "react";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Clock, PlugZap } from "lucide-react";
import { formatCo2, formatWh } from "../format";
import { color } from "../theme";

// Highlight-vs-context: the cleanest window in green, other hours recede in grey;
// your use is one series in blue.
const CLEAN = color("viz-green");
const CONTEXT = color("viz-grey", 0.55);
const USE = color("viz-blue");
const SURFACE = color("surface");

const hourLabel = (h) => `${h % 12 || 12}${h < 12 ? "a" : "p"}`;
const inWindow = (h, w) => w && (h - w.start_hour + 24) % 24 < (w.end_hour - w.start_hour + 24) % 24;

function HourTooltip({ active, payload, format }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg bg-surface border border-line p-2 shadow-pop text-xs">
      <div className="text-ink-soft font-medium">
        {d.label}
        {d.clean && <span className="text-pos"> · cleanest</span>}
      </div>
      <div className="text-ink font-semibold tabular-nums">{format(payload[0].value)}</div>
    </div>
  );
}

// Recharts only recognizes its own axis elements, so the shared hour axis is a set of props.
const HOUR_AXIS = {
  dataKey: "hour",
  tick: { fill: color("ink-muted"), fontSize: 11 },
  tickLine: false,
  axisLine: false,
  interval: 2,
  tickFormatter: hourLabel,
};
const Y_AXIS = { tick: { fill: color("ink-muted"), fontSize: 11 }, tickLine: false, axisLine: false };

function Tile({ title, value, sub, highlight, accent = "text-ink" }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "border-pos/30 bg-pos/[0.06]" : "border-line bg-sunken"}`}>
      <div className={`text-xs font-medium ${highlight ? "text-pos" : "text-ink-muted"}`}>{title}</div>
      <div className={`text-base font-bold mt-0.5 tabular-nums ${accent}`}>{value}</div>
      <div className="text-xs text-ink-muted mt-0.5">{sub}</div>
    </div>
  );
}

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
    <section className="dash-card p-5 min-w-0">
      <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-2">
        <div className="min-w-0">
          <h2 className="card-title flex items-center gap-2">
            <Clock className="w-4 h-4 text-ink-muted" /> Cleanest hours to run AI
          </h2>
          <div className="card-sub mt-0.5">
            Grid carbon intensity by hour ({info.zone}
            {info.source === "forecast" ? ", next 24 h forecast" : info.source === "history" ? ", last 24 h" : ""}) and
            when this device runs AI
          </div>
        </div>
        {info.now && (
          <span className="tech-tag tech-tag-neutral tabular-nums">Grid now: {Math.round(info.now.g_per_kwh)} g CO₂/kWh</span>
        )}
      </div>

      {plan && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
          <Tile
            highlight
            title={`Cleanest ${plan.window_hours} h`}
            value={plan.cleanest.label}
            sub={`${Math.round(plan.cleanest.g_per_kwh)} g CO₂/kWh`}
          />
          <Tile
            title="Your AI hours"
            value={plan.peak_use_label ? `Peak ${plan.peak_use_label}` : "No AI use yet"}
            sub={plan.weighted_g_per_kwh != null ? `${Math.round(plan.weighted_g_per_kwh)} g CO₂/kWh on average` : "—"}
          />
          <Tile
            title="Shift batch jobs"
            value={plan.shift ? `-${formatCo2(plan.shift.co2_saved_kg)} / mo` : "Already clean"}
            accent="text-pos"
            sub={plan.shift ? `${Math.round(plan.shift.share * 100)}% of AI energy moved · bill unchanged` : "Your AI runs in clean hours"}
          />
        </div>
      )}

      {hasGrid ? (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-ink-muted mb-2">
            <span>Grid g CO₂ / kWh</span>
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
                <CartesianGrid stroke={color("line")} vertical={false} />
                <XAxis {...HOUR_AXIS} />
                <YAxis {...Y_AXIS} />
                <Tooltip
                  content={<HourTooltip format={(v) => (v == null ? "no data" : `${Math.round(v)} g CO₂/kWh`)} />}
                  cursor={{ fill: color("ink", 0.04) }}
                />
                <Bar dataKey="g" radius={[3, 3, 0, 0]} stroke={SURFACE} strokeWidth={2}>
                  {data.map((d) => (
                    <Cell key={d.hour} fill={d.clean ? CLEAN : CONTEXT} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="mt-4 p-3 rounded-lg border border-warn/25 bg-warn/[0.06] text-sm text-ink-soft flex gap-2.5">
          <PlugZap className="w-4 h-4 text-warn shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-semibold text-warn text-sm">Hourly grid data not connected</div>
            <p className="text-xs leading-relaxed">
              The DOE grid factor is one number for the whole year, so it can't tell clean hours from dirty ones.
              Get a free personal token at app.electricitymaps.com, then add{" "}
              <code className="font-mono text-[11px] px-1 py-0.5 rounded bg-sunken border border-line text-ink">ELECTRICITYMAPS_TOKEN=…</code> to{" "}
              <code className="font-mono text-[11px] px-1 py-0.5 rounded bg-sunken border border-line text-ink">backend/.env</code>{" "}
              and restart the backend.
            </p>
            {info.configured && info.error && <p className="text-xs text-neg">Electricity Maps: {info.error}</p>}
          </div>
        </div>
      )}

      <div className="mt-4">
        <div className="text-xs text-ink-muted mb-2">Your AI energy by hour · Wh per day, last 30 days</div>
        {hasUse ? (
          <div className="h-28">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
                <CartesianGrid stroke={color("line")} vertical={false} />
                <XAxis {...HOUR_AXIS} />
                <YAxis {...Y_AXIS} />
                <Tooltip content={<HourTooltip format={(v) => `${formatWh(v)} a day`} />} cursor={{ fill: color("ink", 0.04) }} />
                <Bar dataKey="wh" fill={USE} radius={[3, 3, 0, 0]} stroke={SURFACE} strokeWidth={2} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="p-4 text-center text-sm text-ink-muted inset-panel">No AI use measured on this device yet.</div>
        )}
      </div>
    </section>
  );
}
