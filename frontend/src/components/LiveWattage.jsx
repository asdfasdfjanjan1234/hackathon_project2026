import { useEffect, useState, useMemo } from "react";
import { api } from "../api/client";
import {
  Activity,
  Cpu,
  Server,
  Terminal,
  Layers,
  Radio,
} from "lucide-react";
import { formatWatts } from "../format";

export default function LiveWattage({ onReadingChange }) {
  const [reading, setReading] = useState(null);
  const [history, setHistory] = useState([24, 28, 35, 42, 38, 45, 52, 48, 42, 47]);

  useEffect(() => {
    let isMounted = true;
    const poll = async () => {
      try {
        const data = await api.live();
        if (!isMounted) return;
        setReading(data);
        if (onReadingChange) onReadingChange(data);
        if (data?.watts != null) {
          setHistory((prev) => [...prev.slice(-15), data.watts]);
        }
      } catch (err) {
        // Silently preserve state
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [onReadingChange]);

  const currentWatts = reading?.watts ?? 47.7;
  const isSimulated = reading?.simulated ?? true;
  const sourceName = reading?.source ?? (isSimulated ? "SIMULATED" : "APPLE SILICON");

  // Calibrated scale: 0 to 120 Watts
  const maxWatts = 120;
  const clampedWatts = Math.min(Math.max(currentWatts, 0), maxWatts);
  const percentage = Math.round((clampedWatts / maxWatts) * 100);

  // Precision Semicircle SVG Arc Geometry (180 degrees)
  // Center: (120, 116), Radius: 82. Arc length = PI * 82 = 257.61
  const radius = 82;
  const arcLength = Math.PI * radius; // 257.61
  const strokeDashoffset = arcLength * (1 - clampedWatts / maxWatts);

  // Status configuration
  let powerState = {
    label: "NOMINAL LOAD",
    color: "#38BDF8", // Instrument Cyan
    stroke: "rgba(56, 189, 248, 0.35)",
    bg: "rgba(56, 189, 248, 0.08)",
  };
  if (currentWatts > 80) {
    powerState = {
      label: "PEAK GPU DRAW",
      color: "#FB7185", // Crimson
      stroke: "rgba(244, 63, 94, 0.35)",
      bg: "rgba(244, 63, 94, 0.08)",
    };
  } else if (currentWatts < 25) {
    powerState = {
      label: "IDLE STANDBY",
      color: "#94A3B8", // Slate
      stroke: "rgba(148, 163, 184, 0.3)",
      bg: "rgba(148, 163, 184, 0.08)",
    };
  }

  // Process attribution breakdown
  const processList = useMemo(() => {
    if (reading?.apps && Array.isArray(reading.apps) && reading.apps.length > 0) {
      return reading.apps.map((a) => ({
        name: a.name,
        arch: a.kind === "local" ? "Metal GPU" : "Host Client",
        watts: a.watts,
        cpu: `${(a.cpu_percent || 0).toFixed(1)}%`,
        icon: a.kind === "local" ? Server : Terminal,
      }));
    }

    const totalAi = Math.max(10, currentWatts * 0.7);
    return [
      {
        name: "ollama (llama3:8b)",
        arch: "Apple Silicon Metal GPU",
        watts: totalAi * 0.62,
        cpu: "34.2%",
        icon: Server,
      },
      {
        name: "claude-code (node)",
        arch: "CLI Agent Client",
        watts: totalAi * 0.23,
        cpu: "8.5%",
        icon: Terminal,
      },
      {
        name: "cursor (electron)",
        arch: "IDE Agent IPC",
        watts: totalAi * 0.15,
        cpu: "4.1%",
        icon: Layers,
      },
    ];
  }, [reading, currentWatts]);

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
            isSimulated ? "tech-tag-sim" : "tech-tag-live"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isSimulated ? "bg-amber-400" : "bg-sky-400 animate-pulse"
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

            {/* Calibration Tick Notches */}
            {/* 0W: 180° */}
            <line x1="38" y1="116" x2="31" y2="116" stroke="#475569" strokeWidth="1.5" />
            {/* 30W: 135° */}
            <line x1="62.0" y1="58.0" x2="57.0" y2="53.0" stroke="#475569" strokeWidth="1.5" />
            {/* 60W: 90° (Apex) */}
            <line x1="120" y1="34" x2="120" y2="27" stroke="#475569" strokeWidth="1.5" />
            {/* 90W: 45° */}
            <line x1="178.0" y1="58.0" x2="183.0" y2="53.0" stroke="#475569" strokeWidth="1.5" />
            {/* 120W: 0° */}
            <line x1="202" y1="116" x2="209" y2="116" stroke="#475569" strokeWidth="1.5" />

            {/* Calibration Numerical Labels */}
            <text x="26" y="132" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="middle">0W</text>
            <text x="48" y="47" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="end">30W</text>
            <text x="120" y="22" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="middle">60W</text>
            <text x="192" y="47" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="start">90W</text>
            <text x="214" y="132" fill="#64748B" fontSize="9" fontFamily="'JetBrains Mono', monospace" textAnchor="middle">120W</text>

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
              {currentWatts.toFixed(1)}
              <tspan fontSize="15" fontWeight="600" fill="#38BDF8"> W</tspan>
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
            30S HISTORY:
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
      </div>

      {/* Active AI Workload Breakdown */}
      <div className="pt-3 border-t border-white/5 space-y-2">
        <div className="flex items-center justify-between text-[10px] font-mono font-semibold text-slate-400 uppercase tracking-wider">
          <span>PROCESS / RUNTIME</span>
          <span>ATTRIBUTED DRAW</span>
        </div>

        <div className="space-y-1.5">
          {processList.map((proc, i) => {
            const Icon = proc.icon || Terminal;
            return (
              <div
                key={i}
                className="flex items-center justify-between p-2 rounded bg-black/30 border border-white/5 text-xs font-mono"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 h-5 rounded bg-white/[0.04] border border-white/5 flex items-center justify-center text-slate-400 shrink-0">
                    <Icon className="w-3 h-3" />
                  </div>
                  <div className="truncate min-w-0">
                    <div className="text-slate-200 font-medium truncate text-[11px]">
                      {proc.name}
                    </div>
                    <div className="text-[9px] text-slate-400 truncate">
                      {proc.arch} · CPU {proc.cpu}
                    </div>
                  </div>
                </div>

                <div className="text-right shrink-0 font-bold text-slate-100 tabular-nums text-xs ml-2">
                  {formatWatts(proc.watts)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
