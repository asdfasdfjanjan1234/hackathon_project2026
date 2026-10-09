import { useState } from "react";
import {
  Bell,
  Menu,
  SlidersHorizontal,
} from "lucide-react";
import { peso } from "../format";
import ThemeToggle from "./ThemeToggle";
import Figures from "./Figures";
import { useChangeKey } from "../motion";
import { ALERT_LEVELS } from "../alerts";

const OS_NAMES = { macos: "macOS", windows: "Windows", linux: "Linux" };

// The left edge of each alert, and the bell's dot, in the most urgent level's colour.
const LEVEL_EDGE = { alert: "border-l-neg", warn: "border-l-warn", tip: "border-l-pos", info: "border-l-line-strong" };
const LEVEL_DOT = { alert: "bg-neg", warn: "bg-warn", tip: "bg-pos" };

function deviceLabel(system) {
  if (!system) return "Detecting device…";
  const model = system.device?.model || system.cpu || "Unknown device";
  return `${model} · ${OS_NAMES[system.os] || system.os}`;
}

// What the live power number is based on right now.
function sensorStatus(reading) {
  if (!reading) return { text: "Connecting", live: false };
  if (reading.source === "collector") return { text: "Reading device", live: true };
  if (reading.estimated) return { text: "Estimated power", live: false };
  return { text: "Sensor online", live: true };
}

export default function TopBar({
  dateRange = "30d",
  setDateRange,
  electricityRate,
  monthlyBudget,
  onOpenMobileMenu,
  onOpenSettings,
  system,
  liveReading,
  alerts = [],
  onOpenView,
  onAsk,
}) {
  const [showNotifications, setShowNotifications] = useState(false);
  const status = sensorStatus(liveReading);
  const flashKey = useChangeKey(liveReading);
  // Alerts arrive most urgent first; notes alone don't light the bell.
  const dot = LEVEL_DOT[alerts[0]?.level];
  const closeAnd = (fn) => () => {
    setShowNotifications(false);
    fn();
  };

  return (
    <header className="h-16 bg-surface/80 backdrop-blur border-b border-line shadow-card px-3 sm:px-6 lg:px-8 flex items-center justify-between gap-3 sticky top-0 z-20">
      {/* Left: Mobile hamburger menu & Title */}
      <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
        {/* Hamburger Menu on Mobile */}
        <button onClick={onOpenMobileMenu} className="md:hidden btn-icon" aria-label="Open navigation drawer">
          <Menu className="w-5 h-5" />
        </button>

        <div className="min-w-0">
          <div className="flex items-center gap-2.5">
            <h1 className="text-base font-bold tracking-tight text-ink truncate md:sr-only">Kilo What?</h1>
            <span className="hidden xs:inline-flex items-center gap-1.5 text-xs font-medium text-ink-soft shrink-0">
              <span key={flashKey} className={`reading-flash w-2 h-2 rounded-full ${status.live ? "bg-pos" : "bg-warn"}`} />
              {status.text}
            </span>
          </div>

          <div className="text-xs text-ink-muted hidden lg:flex items-center gap-2 mt-0.5">
            <span className="truncate max-w-[18rem]" title={system?.cpu}>{deviceLabel(system)}</span>
            <span aria-hidden>·</span>
            <button
              onClick={onOpenSettings}
              className="hover:text-accent transition-colors tabular-nums"
              title="Click to configure tariff"
            >
              Tariff: <span className="font-semibold text-ink-soft">{peso(electricityRate)}</span> / kWh
            </button>
            <span aria-hidden>·</span>
            <button
              onClick={onOpenSettings}
              className="hover:text-accent transition-colors tabular-nums"
              title="Click to configure budget cap"
            >
              Cap: <span className="font-semibold text-ink-soft">{peso(monthlyBudget)}</span> / mo
            </button>
          </div>
        </div>
      </div>

      {/* Right Controls: Sampling window, telemetry refresh, alerts */}
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {/* Quick Clickable Tariff/Budget Chip on Tablet/Laptop */}
        <button
          onClick={onOpenSettings}
          className="btn hidden sm:inline-flex md:hidden xl:inline-flex tabular-nums"
          title="Configure Tariff & Hardware Cap"
        >
          <SlidersHorizontal className="w-3.5 h-3.5 text-ink-muted" />
          <span>{peso(electricityRate)}/kWh</span>
        </button>

        {/* Time Window Selector (7D, 30D, MTD) */}
        <div className="seg" role="group" aria-label="Time window">
          {[
            { id: "7d", label: "7D" },
            { id: "30d", label: "30D" },
            { id: "month", label: "MTD" },
          ].map((range) => (
            <button
              key={range.id}
              onClick={() => setDateRange && setDateRange(range.id)}
              aria-pressed={dateRange === range.id}
              className={`seg-item px-2 sm:px-2.5 ${dateRange === range.id ? "seg-item-active" : ""}`}
            >
              {range.label}
            </button>
          ))}
        </div>

        <ThemeToggle className="hidden sm:flex" />

        {/* Telemetry Alert Log */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="btn-icon relative"
            title="System Alert Log"
            aria-label={`Alerts${alerts.length ? ` (${alerts.length})` : ""}`}
            aria-expanded={showNotifications}
          >
            <Bell className="w-4 h-4" />
            {dot && <span className={`absolute top-1.5 right-1.5 w-2 h-2 rounded-full ring-2 ring-surface ${dot}`} />}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-[min(22rem,calc(100vw-1.5rem))] rounded-xl bg-surface border border-line shadow-pop p-3 z-50 text-sm">
              <div className="flex items-center justify-between pb-2 border-b border-line mb-2.5">
                <span className="font-bold text-ink">Alerts</span>
                <span className="text-xs font-semibold text-ink-muted tabular-nums">{alerts.length} active</span>
              </div>
              <div className="space-y-2 text-xs max-h-[60vh] overflow-y-auto">
                {alerts.length === 0 && (
                  <div className="p-2 text-ink-muted">Nothing needs attention: the forecast is within budget.</div>
                )}
                {alerts.map((a) => {
                  const level = ALERT_LEVELS[a.level] || ALERT_LEVELS.info;
                  return (
                    <div
                      key={a.id}
                      className={`p-2.5 rounded-lg border border-line border-l-2 bg-sunken text-ink-soft leading-relaxed ${LEVEL_EDGE[a.level] || LEVEL_EDGE.info}`}
                    >
                      <div className="flex items-start gap-1.5 mb-1">
                        <span className={`tech-tag shrink-0 ${level.tag}`}>{level.label}</span>
                        <span className="font-semibold text-ink min-w-0 pt-px">{a.title}</span>
                      </div>
                      <Figures text={a.text} />
                      <div className="flex items-center gap-3 mt-1.5">
                        {onOpenView && a.view && (
                          <button onClick={closeAnd(() => onOpenView(a.view))} className="link">Show me</button>
                        )}
                        {onAsk && (
                          <button onClick={closeAnd(() => onAsk(`Explain this alert: ${a.title}`))} className="link">
                            Ask Kilo
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
