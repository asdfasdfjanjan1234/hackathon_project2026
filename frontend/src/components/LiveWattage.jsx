import { useEffect, useState, useMemo } from "react";
import {
  Server,
  Terminal,
  Info,
  ChevronDown,
} from "lucide-react";
import { formatWatts } from "../format";
import { ACTIVITY, METRICS, explainApp, explainReading } from "../explain";
import { color } from "../theme";
import AppPowerParts from "./AppPowerParts";
import PowerSplit from "./PowerSplit";

// Dial full-scale steps: the smallest that fits the readings, so a 5 W laptop and a
// 400 W gaming PC both use the whole arc.
const SCALES = [10, 20, 30, 60, 120, 300, 600, 1200, 2400];
const HISTORY = 15;

// The reading is polled once in App so it stays live whichever view is open.
export default function LiveWattage({ reading }) {
  const [history, setHistory] = useState([]);
  const [showMetrics, setShowMetrics] = useState(false);

  useEffect(() => {
    if (reading?.watts != null) {
      setHistory((prev) => [...prev.slice(-(HISTORY - 1)), reading.watts]);
    }
  }, [reading]);

  const currentWatts = reading?.watts ?? 0;
  const collecting = reading?.source === "collector";
  const estimated = reading?.estimated ?? false;
  const sourceName = !reading ? "No reading" : estimated ? "Estimated" : collecting ? "Measured" : reading.source;

  const peak = Math.max(currentWatts, ...history, 1);
  const maxWatts = SCALES.find((s) => s >= peak * 1.15) || SCALES[SCALES.length - 1];
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const v = maxWatts * f;
    return Number.isInteger(v) ? v : v.toFixed(1);
  });
  const clampedWatts = Math.min(Math.max(currentWatts, 0), maxWatts);
  const percentage = Math.round((clampedWatts / maxWatts) * 100);

  // Semicircle arc geometry (180 degrees)
  // Center: (120, 116), Radius: 82. Arc length = PI * 82 = 257.61
  const radius = 82;
  const arcLength = Math.PI * radius; // 257.61
  const strokeDashoffset = arcLength * (1 - clampedWatts / maxWatts);

  // Load relative to the dial's scale
  let powerState = { label: "Nominal load", tone: "accent" };
  if (percentage > 80) powerState = { label: "High load", tone: "warn" };
  else if (percentage < 25) powerState = { label: "Low load", tone: "ink-muted" };

  // Watts per AI app, as attributed by the device reader: its share of the machine's power by CPU and GPU use.
  const processList = useMemo(
    () =>
      (reading?.apps || []).map((a) => ({
        name: a.name || a.model || a.app,
        arch: `${a.kind === "local" ? "Local model" : "AI app"}${a.host ? ` · in ${a.host}` : ""}${a.effort ? ` · ${a.effort} effort` : ""}`,
        watts: a.watts,
        cpu: `${(a.cpu_percent || 0).toFixed(1)}%`,
        app: a,
        activity: ACTIVITY[a.activity],
        why: explainApp(a),
        icon: a.kind === "local" ? Server : Terminal,
      })),
    [reading]
  );
  const summary = useMemo(() => explainReading(reading), [reading]);

  if (!reading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-w-0">
        <div className="dash-card p-5 h-80 animate-pulse" />
        <div className="dash-card p-5 h-80 animate-pulse" />
      </div>
    );
  }

  const tick = color("line-strong");
  const label = { fill: color("ink-muted"), fontSize: 10, fontFamily: "inherit" };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-w-0 items-stretch">
      {/* 1. Left Card: Active power draw monitor dial, sparkline, diagnostic, and power breakdown */}
      <section className="dash-card p-5 flex flex-col justify-between min-w-0 h-full">
        <div>
          {/* Header */}
          <div className="flex items-start justify-between pb-4 border-b border-line gap-2">
            <div className="min-w-0">
              <h2 className="card-title truncate">Active power draw monitor</h2>
              <div className="card-sub truncate mt-0.5">Sensor bus: {sourceName.toLowerCase()}</div>
            </div>
            <span className={`tech-tag shrink-0 ${estimated ? "tech-tag-sim" : "tech-tag-live"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${estimated ? "bg-warn" : "bg-accent"}`} />
              {sourceName}
            </span>
          </div>

          {/* Dial */}
          <div className="py-3 flex flex-col items-center justify-center min-w-0">
            <div className="w-full max-w-[280px]">
              <svg
                viewBox="0 0 240 142"
                className="w-full h-auto overflow-visible"
                role="img"
                aria-label={`${formatWatts(currentWatts)}, ${powerState.label.toLowerCase()}, ${percentage}% of a ${maxWatts} W scale`}
              >
                {/* Background Arc Track */}
                <path d="M 38 116 A 82 82 0 0 1 202 116" fill="none" stroke={color("sunken")} strokeWidth="10" strokeLinecap="round" />
                <path d="M 38 116 A 82 82 0 0 1 202 116" fill="none" stroke={color("line")} strokeWidth="10" strokeLinecap="round" strokeOpacity="0.6" />

                {/* Progress Arc */}
                <path
                  d="M 38 116 A 82 82 0 0 1 202 116"
                  fill="none"
                  stroke={color(powerState.tone)}
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={arcLength}
                  strokeDashoffset={strokeDashoffset}
                  style={{ transition: "stroke-dashoffset 0.5s ease-out, stroke 0.3s" }}
                />

                {/* Calibration Tick Notches at 0, ¼, ½, ¾ and full scale */}
                <line x1="38" y1="116" x2="31" y2="116" stroke={tick} strokeWidth="1.5" />
                <line x1="62.0" y1="58.0" x2="57.0" y2="53.0" stroke={tick} strokeWidth="1.5" />
                <line x1="120" y1="34" x2="120" y2="27" stroke={tick} strokeWidth="1.5" />
                <line x1="178.0" y1="58.0" x2="183.0" y2="53.0" stroke={tick} strokeWidth="1.5" />
                <line x1="202" y1="116" x2="209" y2="116" stroke={tick} strokeWidth="1.5" />

                {/* Calibration Numerical Labels */}
                <text x="26" y="132" {...label} textAnchor="middle">{ticks[0]} W</text>
                <text x="48" y="47" {...label} textAnchor="end">{ticks[1]} W</text>
                <text x="120" y="20" {...label} textAnchor="middle">{ticks[2]} W</text>
                <text x="192" y="47" {...label} textAnchor="start">{ticks[3]} W</text>
                <text x="214" y="132" {...label} textAnchor="middle">{ticks[4]} W</text>

                {/* Digital Readout */}
                <text
                  x="120"
                  y="84"
                  textAnchor="middle"
                  fill={color("ink")}
                  fontFamily="inherit"
                  fontWeight="600"
                  fontSize="30"
                  letterSpacing="-0.02em"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {currentWatts >= 1000 ? (currentWatts / 1000).toFixed(2) : currentWatts.toFixed(1)}
                  <tspan fontSize="15" fontWeight="500" fill={color("ink-muted")}>
                    {currentWatts >= 1000 ? " kW" : " W"}
                  </tspan>
                </text>

                {/* Load status, inside the arc */}
                <text
                  x="120"
                  y="106"
                  textAnchor="middle"
                  fill={color(powerState.tone)}
                  fontSize="11"
                  fontWeight="500"
                  fontFamily="inherit"
                >
                  {powerState.label} · {percentage}%
                </text>
              </svg>
            </div>

            {/* 30s history */}
            <div className="w-full max-w-[280px] flex items-center justify-between text-xs text-ink-muted mt-2 px-3 py-1.5 inset-panel">
              <span className="shrink-0">{HISTORY * 2}s history</span>
              <div className="flex items-end gap-1 h-4 mx-2" aria-hidden>
                {history.map((val, idx) => (
                  <div
                    key={idx}
                    className="w-1.5 bg-accent/60 rounded-t-sm transition-all duration-300"
                    style={{ height: `${Math.max(2, Math.min(16, (val / maxWatts) * 16))}px` }}
                    title={`${val.toFixed(1)} W`}
                  />
                ))}
              </div>
              <span className="text-ink font-medium tabular-nums shrink-0">{currentWatts.toFixed(1)} W</span>
            </div>

            {/* Why the computer draws what it draws, updated with every reading */}
            {summary.length > 0 && (
              <div className="w-full mt-3 p-3 rounded-lg bg-accent/[0.06] border border-accent/15 text-[13px] leading-relaxed text-ink-soft">
                <div className="flex items-center gap-1.5 text-xs font-medium text-accent mb-1">
                  <Info className="w-3.5 h-3.5" />
                  Right now
                </div>
                {summary.map((line, i) => (
                  <p key={i} className={i === 0 ? "text-ink" : ""}>{line}</p>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Where the watts go: by part and by use */}
        <div className="mt-2">
          <PowerSplit reading={reading} />
        </div>
      </section>

      {/* 2. Right Card: Active AI Workload Breakdown (Scrollable Process List) */}
      <section className="dash-card p-5 flex flex-col justify-between min-w-0 h-full">
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <div className="flex items-start justify-between pb-4 border-b border-line gap-2">
            <div className="min-w-0">
              <h2 className="card-title truncate">Active AI workload breakdown</h2>
              <div className="card-sub truncate mt-0.5">Attributed machine draw per AI process</div>
            </div>
            <span className="tech-tag tech-tag-neutral shrink-0 tabular-nums">
              {processList.length} {processList.length === 1 ? "runtime" : "runtimes"}
            </span>
          </div>

          <div className="flex items-center justify-between text-xs font-medium text-ink-muted py-2.5">
            <span>Process / runtime</span>
            <span>Attributed draw</span>
          </div>

          {/* Scrollable process list container */}
          <div className="flex-1 max-h-[360px] overflow-y-auto space-y-1.5 pr-1 min-h-[140px]">
            {processList.length === 0 && (
              <div className="p-3 inset-panel text-xs text-ink-muted">
                {collecting
                  ? "No AI apps running right now."
                  : "Start the device reader (This Device) to measure watts per AI app."}
              </div>
            )}
            {processList.map((proc, i) => {
              const Icon = proc.icon || Terminal;
              return (
                <div
                  key={i}
                  className={`flex items-start justify-between p-2.5 inset-panel ${proc.app.activity === "idle" ? "opacity-70" : ""}`}
                >
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <Icon className="w-4 h-4 text-ink-muted shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-sm font-medium text-ink truncate">{proc.name}</span>
                        {proc.activity && (
                          <span className={`shrink-0 px-1.5 rounded-full border text-[11px] leading-4 ${proc.activity.chip}`}>
                            {proc.activity.label}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-ink-muted truncate tabular-nums">
                        {proc.arch} · CPU {proc.cpu}
                      </div>
                      {proc.why && <div className="text-xs text-ink-soft leading-snug mt-1">{proc.why}</div>}
                      <AppPowerParts app={proc.app} />
                    </div>
                  </div>

                  <div className="text-right shrink-0 font-semibold text-ink tabular-nums text-sm ml-2">
                    {formatWatts(proc.watts)}
                  </div>
                </div>
              );
            })}
          </div>

          {processList.length > 0 && (
            <div className="text-xs text-ink-muted mt-2">
              Machine total {estimated ? "estimated" : "measured"} · per-app split calculated from CPU/GPU share
            </div>
          )}
        </div>

        {/* Footnote / Explanation accordion */}
        <div className="pt-3 border-t border-line mt-3">
          <button
            type="button"
            onClick={() => setShowMetrics((v) => !v)}
            aria-expanded={showMetrics}
            className="link"
          >
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showMetrics ? "rotate-180" : ""}`} />
            What do these numbers mean?
          </button>
          {showMetrics && (
            <dl className="space-y-2 p-3 inset-panel text-xs leading-snug mt-2">
              {METRICS.map((m) => (
                <div key={m.term}>
                  <dt className="font-medium text-ink">{m.term}</dt>
                  <dd className="text-ink-soft">{m.text}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>
    </div>
  );
}
