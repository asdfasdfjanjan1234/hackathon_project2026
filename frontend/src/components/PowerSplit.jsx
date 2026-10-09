import { formatAppWatts } from "../format";

// The machine's parts, as read by the device reader (backend measurement.py Sensors.components).
const PARTS = [
  { key: "cpu", label: "CPU", bar: "bg-viz-blue", text: "text-ink-soft" },
  { key: "gpu", label: "GPU", bar: "bg-viz-violet", text: "text-ink-soft" },
  { key: "memory", label: "RAM", bar: "bg-viz-amber", text: "text-ink-soft" },
  { key: "disk", label: "Disk", bar: "bg-viz-green", text: "text-ink-soft" },
];
const OTHER = { bar: "bg-viz-grey", text: "text-ink-soft" };

const isMeasured = (source) => source && source !== "estimated";

/**
 * Where the reading's watts go, two ways:
 *   byPart: CPU, GPU, RAM, disk, and the rest (screen, Wi-Fi, fans, board).
 *   byUse:  AI apps, the baseline the machine draws doing nothing, and everything else.
 * Returns null when the reading has no per-part data (device reader not running).
 */
export function splitReading(reading) {
  const components = reading?.components;
  if (!components || !Object.keys(components).length) return null;
  const total = reading.watts ?? 0;

  const byPart = PARTS.filter((p) => components[p.key]).map((p) => ({
    ...p,
    watts: components[p.key].watts || 0,
    measured: isMeasured(components[p.key].source),
  }));
  const partsSum = byPart.reduce((s, p) => s + p.watts, 0);
  if (components.other) {
    // Measured whole-machine power minus the parts above.
    byPart.push({ key: "other", label: "Screen, Wi-Fi, fans…", ...OTHER, watts: components.other.watts || 0, measured: true });
  } else if (total - partsSum > 0.05) {
    // No whole-machine sensor: the formula's total minus the parts, mostly its idle term.
    byPart.push({ key: "other", label: "Rest of system", ...OTHER, watts: total - partsSum, measured: false });
  }

  const apps = reading.apps || [];
  const ai = Math.min(reading.ai_watts ?? apps.reduce((s, a) => s + (a.watts || 0), 0), total);
  const baseline = Math.min(reading.power_model?.idle_watts ?? 0, Math.max(total - ai, 0));
  const byUse = [
    { key: "ai", label: "AI apps", bar: "bg-accent", text: "text-ink-soft", watts: ai, measured: !reading.estimated },
    { key: "rest", label: "Other apps & OS", bar: "bg-viz-grey", text: "text-ink-soft",
      watts: Math.max(total - ai - baseline, 0), measured: false },
    { key: "baseline", label: "Baseline (idle)", bar: "bg-line-strong", text: "text-ink-soft",
      watts: baseline, measured: false },
  ];

  return { byPart, byUse };
}

function Breakdown({ title, rows }) {
  const total = rows.reduce((s, r) => s + r.watts, 0);
  const pct = (w) => (total > 0 ? Math.round((w / total) * 100) : 0);
  return (
    <div className="space-y-2 min-w-0">
      <div className="text-xs font-medium text-ink-muted">{title}</div>
      <div className="w-full flex h-2 bg-line rounded-full overflow-hidden gap-px">
        {total > 0 &&
          rows.map((r) => (
            <div key={r.key} className={r.bar} style={{ width: `${(r.watts / total) * 100}%` }} title={`${r.label}: ${formatAppWatts(r.watts)}`} />
          ))}
      </div>
      <div className="space-y-1">
        {rows.map((r) => (
          <div key={r.key} className="flex items-center justify-between gap-2 text-xs tabular-nums">
            <span className="flex items-center gap-1.5 min-w-0">
              <span className={`w-2 h-2 rounded-full shrink-0 ${r.bar}`} />
              <span className={`truncate ${r.text}`}>{r.label}</span>
              <span className="text-[11px] text-ink-muted shrink-0">{r.measured ? "meas." : "est."}</span>
            </span>
            <span className="text-ink shrink-0">
              {formatAppWatts(r.watts)} <span className="text-ink-muted">· {pct(r.watts)}%</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Where the computer's watts go: by hardware part and by what's using them.
export default function PowerSplit({ reading }) {
  const split = splitReading(reading);
  if (!split) return null;
  return (
    <div className="w-full mt-3 p-3 inset-panel space-y-4">
      <Breakdown title="Where the watts go · by part" rows={split.byPart} />
      <Breakdown title="Where the watts go · by use" rows={split.byUse} />
    </div>
  );
}
