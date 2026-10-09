import { formatAppWatts, formatMb } from "../format";

// The parts of an AI app's watts, as split by the device reader (backend attribution.py).
export const PARTS = [
  { key: "cpu", label: "CPU", bar: "bg-sky-400", text: "text-sky-300" },
  { key: "gpu", label: "GPU", bar: "bg-violet-400", text: "text-violet-300" },
  { key: "memory", label: "RAM", bar: "bg-amber-400", text: "text-amber-300" },
];

// One bar split by `values` (same order as PARTS); empty when they sum to zero.
export function PartsBar({ values, className = "h-1" }) {
  const total = values.reduce((s, v) => s + (v || 0), 0);
  return (
    <div className={`w-full flex bg-slate-800 rounded-sm overflow-hidden ${className}`}>
      {total > 0 &&
        PARTS.map((p, i) => (
          <div key={p.key} className={p.bar} style={{ width: `${((values[i] || 0) / total) * 100}%` }} />
        ))}
    </div>
  );
}

// CPU / GPU / RAM watts of one app, plus the memory it holds. Readings taken before the
// split was recorded have no parts, so only the memory line shows for them.
export default function AppPowerParts({ app }) {
  const split = app.cpu_watts != null;
  const onGpu = app.vram_mb != null && app.model_mb ? Math.round((app.vram_mb / app.model_mb) * 100) : null;
  return (
    <div className="mt-1 space-y-1 min-w-0">
      {split && (
        <>
          <PartsBar values={PARTS.map((p) => app[`${p.key}_watts`])} />
          <div className="flex flex-wrap gap-x-2 text-[9px] font-mono tabular-nums">
            {PARTS.map((p) => (
              <span key={p.key} className={p.text}>
                {p.label} {formatAppWatts(app[`${p.key}_watts`])}
              </span>
            ))}
          </div>
        </>
      )}
      <div className="text-[9px] font-mono text-slate-500 truncate">
        holds {formatMb(app.rss_mb)} RAM
        {app.vram_mb != null && ` · ${formatMb(app.vram_mb)} VRAM`}
        {onGpu != null && ` · ${onGpu >= 100 ? "runs on GPU" : onGpu <= 0 ? "runs on CPU" : `${onGpu}% on GPU`}`}
      </div>
    </div>
  );
}
