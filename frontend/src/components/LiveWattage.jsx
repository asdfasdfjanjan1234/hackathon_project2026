import { useEffect, useState, useMemo } from "react";
import {
  Server,
  Terminal,
  Radio,
  Info,
  ChevronDown,
} from "lucide-react";
import { formatWatts } from "../format";
import { ACTIVITY, METRICS, explainApp, explainReading } from "../explain";
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
  const sourceName = !reading ? "NO READING" : estimated ? "ESTIMATED" : collecting ? "MEASURED" : reading.source;

  const peak = Math.max(currentWatts, ...history, 1);
  const maxWatts = SCALES.find((s) => s >= peak * 1.15) || SCALES[SCALES.length - 1];
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const v = maxWatts * f;
    return Number.isInteger(v) ? v : v.toFixed(1);
  });
  const clampedWatts = Math.min(Math.max(currentWatts, 0), maxWatts);
  const percentage = Math.round((clampedWatts / maxWatts) * 100);

  // Precision Semicircle SVG Arc Geometry (180 degrees)
  // Center: (120, 116), Radius: 82. Arc length = PI * 82 = 257.61
  const radius = 82;
  const arcLength = Math.PI * radius; // 257.61
  const strokeDashoffset = arcLength * (1 - clampedWatts / maxWatts);

  // Load relative to the dial's scale
  let powerState = {
    label: "NOMINAL LOAD",
    color: "#38BDF8", // Instrument Cyan
    stroke: "rgba(56, 189, 248, 0.35)",
    bg: "rgba(56, 189, 248, 0.08)",
  };
  if (percentage > 80) {
    powerState = {
      label: "HIGH LOAD",
      color: "#FB7185", // Crimson
      stroke: "rgba(244, 63, 94, 0.35)",
      bg: "rgba(244, 63, 94, 0.08)",
    };
  } else if (percentage < 25) {
    powerState = {
      label: "LOW LOAD",
      color: "#94A3B8", // Slate
      stroke: "rgba(148, 163, 184, 0.3)",
      bg: "rgba(148, 163, 184, 0.08)",
    };
  }

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

  if (!reading) return <section className="dash-card p-5 h-80 animate-pulse" />;

  return (
    <section className="dash-card p-4 sm:p-5 flex flex-col justify-between select-none min-w-0">
      {/* Instrumentation Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/5 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider truncate">
              Active Power Draw Monitor
            </h2>
            <div className="text-[10px] font-mono text-slate-400 truncate">
              Sensor Bus: {sourceName.toLowerCase()}
            </div>
          </div>
        </div>

        {/* Status Chip (Amber for simulated, Cyan for live) */}
        <span
          className={`tech-tag shrink-0 ${
            estimated ? "tech-tag-sim" : "tech-tag-live"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              estimated ? "bg-amber-400" : "bg-sky-400 animate-pulse"
            }`}
          />
          {sourceName}
        </span>
      </div>

      {/* Center: Precision SVG Dial Meter (Proportionally Scaled, Zero Clipping) */}
      <div className="py-2 sm:py-3 flex flex-col items-center justify-center min-w-0">
        <div className="w-full max-w-[280px]">
          <svg
            viewBox="0 0 240 142"
            className="w-full h-auto overflow-visible select-none"
          >
            {/* Background Arc Track */}
            <path
              d="M 38 116 A 82 82 0 0 1 202 116"
              fill="none"
              stroke="#1A2234"
              strokeWidth="9"
              strokeLinecap="round"
            />

            {/* Active Cyan Progress Arc */}
            <path
              d="M 38 116 A 82 82 0 0 1 202 116"
              fill="none"
              stroke="#38BDF8"
              strokeWidth="9"
              strokeLinecap="round"
              strokeDasharray={arcLength}
              strokeDashoffset={strokeDashoffset}
              style={{
                transition: "stroke-dashoffset 0.5s ease-out",
              }}
            />

            {/* Calibration Tick Notches at 0, ¼, ½, ¾ and full scale */}
            {/* 0: 180° */}
            <line x1="38" y1="116" x2="31" y2="116" stroke="#475569" strokeWidth="1.5" />
            {/* ¼: 135° */}
            <line x1="62.0" y1="58.0" x2="57.0" y2="53.0" stroke="#475569" strokeWidth="1.5" />
            {/* ½: 90° (Apex) */}
            <line x1="120" y1="34" x2="120" y2="27" stroke="#475569" strokeWidth="1.5" />
            {/* ¾: 45° */}
            <line x1="178.0" y1="58.0" x2="183.0" y2="53.0" stroke="#475569" strokeWidth="1.5" />
            {/* full scale: 0° */}
            <line x1="202" y1="116" x2="209" y2="116" stroke="#475569" strokeWidth="1.5" />

            {/* Calibration Numerical Labels */}
            <text x="26" y="132" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="middle">{ticks[0]}W</text>
            <text x="48" y="47" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="end">{ticks[1]}W</text>
            <text x="120" y="22" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="middle">{ticks[2]}W</text>
            <text x="192" y="47" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="start">{ticks[3]}W</text>
            <text x="214" y="132" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="middle">{ticks[4]}W</text>

            {/* Digital Readout */}
            <text
              x="120"
              y="82"
              textAnchor="middle"
              fill="#FFFFFF"
              fontFamily="'JetBrains Mono', monospace"
              fontWeight="800"
              fontSize="28"
              letterSpacing="-0.02em"
            >
              {currentWatts >= 1000 ? (currentWatts / 1000).toFixed(2) : currentWatts.toFixed(1)}
              <tspan fontSize="15" fontWeight="600" fill="#38BDF8">{currentWatts >= 1000 ? " kW" : " W"}</tspan>
            </text>

            {/* Operational Status Pill (Cleanly Positioned Inside Arc, No Overlap) */}
            <g transform="translate(120, 102)">
              <rect
                x="-58"
                y="-9"
                width="116"
                height="18"
                rx="4"
                fill={powerState.bg}
                stroke={powerState.stroke}
                strokeWidth="1"
              />
              <text
                x="0"
                y="3.5"
                textAnchor="middle"
                fill={powerState.color}
                fontSize="8.5"
                fontWeight="700"
                fontFamily="'JetBrains Mono', monospace"
                letterSpacing="0.04em"
              >
                {powerState.label} · {percentage}%
              </text>
            </g>
          </svg>
        </div>

        {/* 30s Hardware Histogram Bar Ticker */}
        <div className="w-full max-w-[280px] flex items-center justify-between text-[10px] text-slate-400 mt-2 px-3 font-mono bg-black/30 py-1.5 rounded border border-white/5">
          <span className="text-[9px] text-slate-400 uppercase tracking-wider shrink-0">
            {HISTORY * 2}S HISTORY:
          </span>
          <div className="flex items-end gap-1 h-3.5 mx-2">
            {history.map((val, idx) => (
              <div
                key={idx}
                className="w-1.5 bg-sky-500/60 rounded-t-xs transition-all duration-300"
                style={{
                  height: `${Math.max(2, Math.min(14, (val / maxWatts) * 14))}px`,
                }}
                title={`${val.toFixed(1)} W`}
              />
            ))}
          </div>
          <span className="text-[10px] text-sky-400 font-bold tabular-nums shrink-0">
            {currentWatts.toFixed(1)}W
          </span>
        </div>

        {/* Why the computer draws what it draws, updated with every reading */}
        {summary.length > 0 && (
          <div className="w-full mt-2 p-2.5 rounded bg-sky-500/[0.06] border border-sky-500/15 text-[11px] leading-relaxed text-slate-300">
            <div className="flex items-center gap-1.5 text-[9px] font-mono font-semibold text-sky-300 uppercase tracking-wider mb-1">
              <Info className="w-3 h-3" />
              Right now
            </div>
            {summary.map((line, i) => (
              <p key={i} className={i === 0 ? "text-slate-100" : ""}>{line}</p>
            ))}
          </div>
        )}

        <PowerSplit reading={reading} />
      </div>

      {/* Active AI Workload Breakdown */}
      <div className="pt-3 border-t border-white/5 space-y-2">
        <div className="flex items-center justify-between text-[10px] font-mono font-semibold text-slate-400 uppercase tracking-wider">
          <span>PROCESS / RUNTIME</span>
          <span>ATTRIBUTED DRAW</span>
        </div>

        <div className="space-y-1.5">
          {processList.length === 0 && (
            <div className="p-2 rounded bg-black/30 border border-white/5 text-[11px] text-slate-400">
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
                className={`flex items-start justify-between p-2 rounded bg-black/30 border border-white/5 text-xs font-mono ${
                  proc.app.activity === "idle" ? "opacity-60" : ""
                }`}
              >
                <div className="flex items-start gap-2 min-w-0 flex-1">
                  <div className="w-5 h-5 rounded bg-white/[0.04] border border-white/5 flex items-center justify-center text-slate-400 shrink-0">
                    <Icon className="w-3 h-3" />
                  </div>
                  <div className="truncate min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="text-slate-200 font-medium truncate text-[11px]">
                        {proc.name}
                      </span>
                      {proc.activity && (
                        <span className={`shrink-0 px-1 rounded border text-[8.5px] uppercase tracking-wider ${proc.activity.chip}`}>
                          {proc.activity.label}
                        </span>
                      )}
                    </div>
                    <div className="text-[9px] text-slate-400 truncate">
                      {proc.arch} · CPU {proc.cpu}
                    </div>
                    {proc.why && (
                      <div className="text-[10px] font-sans text-slate-400 leading-snug mt-0.5 whitespace-normal">
                        {proc.why}
                      </div>
                    )}
                    <AppPowerParts app={proc.app} />
                  </div>
                </div>

                <div className="text-right shrink-0 font-bold text-slate-100 tabular-nums text-xs ml-2">
                  {formatWatts(proc.watts)}
                </div>
              </div>
            );
          })}
        </div>
        {processList.length > 0 && (
          <div className="text-[9px] font-mono text-slate-500">
            Machine total {estimated ? "estimated" : "measured"} · per-app split calculated from CPU/GPU share
          </div>
        )}

        <button
          type="button"
          onClick={() => setShowMetrics((v) => !v)}
          aria-expanded={showMetrics}
          className="flex items-center gap-1 text-[10px] font-mono text-sky-300 hover:text-sky-200"
        >
          <ChevronDown className={`w-3 h-3 transition-transform ${showMetrics ? "rotate-180" : ""}`} />
          What do these numbers mean?
        </button>
        {showMetrics && (
          <dl className="space-y-1.5 p-2.5 rounded bg-black/30 border border-white/5 text-[11px] leading-snug">
            {METRICS.map((m) => (
              <div key={m.term}>
                <dt className="font-mono font-semibold text-slate-200">{m.term}</dt>
                <dd className="text-slate-400">{m.text}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}
