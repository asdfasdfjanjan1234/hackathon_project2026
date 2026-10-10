import { useMemo } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceArea, ReferenceLine, ResponsiveContainer,
} from "recharts";
import { PlugZap } from "lucide-react";
import { formatCo2, formatWh } from "../format";
import { color } from "../theme";
import { CardHeader, MiniTile } from "./Card";

// Highlight-vs-context: the cleanest window in green, other hours recede in grey;
// your use is one series in blue.
const CLEAN = color("viz-green");
const CLEAN_BAND = color("viz-green", 0.1);
const CONTEXT = color("viz-grey");
const USE = color("viz-blue");
const SURFACE = color("surface");

const hourLabel = (h) => `${h % 12 || 12}${h < 12 ? "a" : "p"}`;
const inWindow = (h, w) => w && (h - w.start_hour + 24) % 24 < (w.end_hour - w.start_hour + 24) % 24;

// The cleanest window as shaded hour ranges; a window across midnight becomes two.
function windowRanges(w) {
  if (!w) return [];
  const last = (w.end_hour + 23) % 24;
  return last >= w.start_hour ? [[w.start_hour, last]] : [[w.start_hour, 23], [0, last]];
}

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
// A band scale puts each hour in the same slot on the line chart as on the bar chart.
const HOUR_AXIS = {
  dataKey: "hour",
  scale: "band",
  tick: { fill: color("ink-muted"), fontSize: 11 },
  tickLine: false,
  axisLine: false,
  interval: 2,
  tickFormatter: hourLabel,
};
const Y_AXIS = { tick: { fill: color("ink-muted"), fontSize: 11 }, tickLine: false, axisLine: false };

export default function CleanHours({ info }) {
  const plan = info?.plan;
  const data = useMemo(
    () =>
      Array.from({ length: 24 }, (_, h) => ({
        hour: h,
        label: `${h % 12 || 12}:00 ${h < 12 ? "AM" : "PM"}`,
        g: info?.intensity?.[h]?.g_per_kwh ?? null,
        gClean: inWindow(h, plan?.cleanest) ? info?.intensity?.[h]?.g_per_kwh ?? null : null,
        wh: (info?.use?.[h]?.kwh_per_day ?? 0) * 1000,
        clean: inWindow(h, plan?.cleanest),
      })),
    [info, plan]
  );
  if (!info) return null;
  const grid = data.map((d) => d.g).filter((g) => g != null);
  const hasGrid = grid.length > 0;
  const hasUse = data.some((d) => d.wh > 0);
  // Luzon's grid only swings a few percent over a day, so the axis zooms to that range;
  // from zero every hour would look the same. A line, not bars, since the axis doesn't start at zero.
  const lo = Math.min(...grid);
  const hi = Math.max(...grid);
  const pad = Math.max(5, (hi - lo) * 0.15);
  const domain = [Math.floor((lo - pad) / 5) * 5, Math.ceil((hi + pad) / 5) * 5];
  const swing = hasGrid && hi > 0 ? (hi - lo) / hi : 0;
  const nowHour = info.now ? new Date(info.now.datetime).getHours() : null;
  const ranges = windowRanges(plan?.cleanest);
  const gap = plan?.weighted_g_per_kwh != null ? plan.weighted_g_per_kwh - plan.cleanest.g_per_kwh : null;

  return (
    <section className="dash-card p-5 min-w-0">
      <CardHeader
        title="Cleanest hours to run AI"
        sub={
          <>
            Grid carbon intensity by hour ({info.zone}
            {info.source === "forecast" ? ", next 24 h forecast" : info.source === "history" ? ", last 24 h" : ""}) and
            when this device runs AI
          </>
        }
      >
        {info.now && (
          <span className="tech-tag tech-tag-neutral tabular-nums">Grid now: {Math.round(info.now.g_per_kwh)} g CO₂/kWh</span>
        )}
      </CardHeader>

      {plan && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
          <MiniTile
            highlight
            title={`Cleanest ${plan.window_hours} h`}
            value={plan.cleanest.label}
            sub={`${Math.round(plan.cleanest.g_per_kwh)} g CO₂/kWh`}
          />
          <MiniTile
            title="Your AI hours"
            value={plan.peak_use_label ? `Peak ${plan.peak_use_label}` : "No AI use yet"}
            sub={plan.weighted_g_per_kwh != null ? `${Math.round(plan.weighted_g_per_kwh)} g CO₂/kWh on average` : "—"}
          />
          <MiniTile
            title="Shift batch jobs"
            value={plan.shift ? `-${formatCo2(plan.shift.co2_saved_kg)} / mo` : gap == null ? "Nothing to shift" : "Little to gain"}
            valueClass={plan.shift ? "text-pos" : "text-ink"}
            sub={
              plan.shift
                ? `${Math.round(plan.shift.share * 100)}% of AI energy moved · bill unchanged`
                : gap == null
                  ? "No AI use measured yet"
                  : `Your hours are only ${Math.max(0, Math.round(gap))} g CO₂/kWh above the cleanest`
            }
          />
        </div>
      )}

      {hasGrid ? (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-ink-muted mb-2">
            <span className="tabular-nums">
              Grid g CO₂ / kWh · {Math.round(lo)}–{Math.round(hi)} over the day ({Math.round(swing * 100)}% swing)
            </span>
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: CLEAN }} /> Cleanest window
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: CONTEXT }} /> Other hours
              </span>
            </span>
          </div>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
                <CartesianGrid stroke={color("line")} vertical={false} />
                {ranges.map(([a, b]) => (
                  <ReferenceArea key={a} x1={a} x2={b} fill={CLEAN_BAND} strokeOpacity={0} ifOverflow="visible" />
                ))}
                <XAxis {...HOUR_AXIS} />
                <YAxis {...Y_AXIS} domain={domain} allowDecimals={false} />
                {nowHour != null && (
                  <ReferenceLine
                    x={nowHour}
                    stroke={color("ink-muted")}
                    strokeDasharray="3 3"
                    label={{ value: "now", position: "insideTopRight", fill: color("ink-muted"), fontSize: 11 }}
                  />
                )}
                <Tooltip
                  content={<HourTooltip format={(v) => (v == null ? "no data" : `${Math.round(v)} g CO₂/kWh`)} />}
                  cursor={{ stroke: color("line-strong") }}
                />
                <Line dataKey="g" type="monotone" stroke={CONTEXT} strokeWidth={2} dot={false} connectNulls
                  activeDot={{ r: 4, stroke: SURFACE, strokeWidth: 2 }} isAnimationActive={false} />
                <Line dataKey="gClean" type="monotone" stroke={CLEAN} strokeWidth={2.5} dot={false}
                  activeDot={false} tooltipType="none" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="notice notice-warn mt-4">
          <PlugZap />
          <div className="space-y-1">
            <div className="font-semibold text-ink text-sm">Hourly grid data not connected</div>
            <p>
              The DOE grid factor is one number for the whole year, so it can't tell clean hours from dirty ones.
              Get a free personal token at app.electricitymaps.com, then add{" "}
              <code className="font-mono text-2xs px-1 py-0.5 rounded bg-sunken border border-line text-ink">ELECTRICITYMAPS_TOKEN=…</code> to{" "}
              <code className="font-mono text-2xs px-1 py-0.5 rounded bg-sunken border border-line text-ink">backend/.env</code>{" "}
              and restart the backend.
            </p>
            {info.configured && info.error && <p className="text-xs text-neg">Electricity Maps: {info.error}</p>}
          </div>
        </div>
      )}

      <div className="mt-4">
        <div className="text-xs text-ink-muted mb-2">
          Your AI energy by hour · Wh per day, last 30 days{ranges.length > 0 && " · cleanest window shaded"}
        </div>
        {hasUse ? (
          <div className="h-28">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
                <CartesianGrid stroke={color("line")} vertical={false} />
                {ranges.map(([a, b]) => (
                  <ReferenceArea key={a} x1={a} x2={b} fill={CLEAN_BAND} strokeOpacity={0} ifOverflow="visible" />
                ))}
                <XAxis {...HOUR_AXIS} />
                <YAxis {...Y_AXIS} />
                <Tooltip content={<HourTooltip format={(v) => `${formatWh(v)} a day`} />} cursor={{ fill: color("ink", 0.04) }} />
                <Bar dataKey="wh" fill={USE} radius={[3, 3, 0, 0]} stroke={SURFACE} strokeWidth={2} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="empty-state">No AI use measured on this device yet.</div>
        )}
      </div>
    </section>
  );
}
