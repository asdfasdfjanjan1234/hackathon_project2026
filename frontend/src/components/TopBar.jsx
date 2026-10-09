import { useState } from "react";
import {
  Bell,
  RefreshCw,
  Menu,
  SlidersHorizontal,
  HardDrive,
  Cpu,
} from "lucide-react";
import { peso } from "../format";

export default function TopBar({
  dateRange = "30d",
  setDateRange,
  onRefresh,
  isRefreshing = false,
  electricityRate = 12.0,
  monthlyBudget = 2000,
  notificationCount = 2,
  onOpenMobileMenu,
  onOpenSettings,
}) {
  const [showNotifications, setShowNotifications] = useState(false);

  return (
    <header className="h-16 bg-panelBg border-b border-white/5 px-3 sm:px-5 lg:px-6 flex items-center justify-between gap-3 sticky top-0 z-20 select-none">
      {/* Left: Mobile hamburger menu & Title */}
      <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
        {/* Hamburger Menu on Mobile */}
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.04] transition-colors"
          aria-label="Open navigation drawer"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-sm sm:text-base font-bold font-mono tracking-tight text-white uppercase truncate">
              AI Power Telemetry
            </h1>
            {/* LIVE SENSOR BADGE: Instrument Cyan, NO GREEN */}
            <span className="hidden xs:inline-flex items-center gap-1 text-[9px] sm:text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/25 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />
              SENSORS ONLINE
            </span>
          </div>

          <div className="text-[10px] sm:text-[11px] font-mono text-slate-400 hidden lg:flex items-center gap-2 mt-0.5">
            <span>BUS: Apple Silicon SoC</span>
            <span>·</span>
            <button
              onClick={onOpenSettings}
              className="hover:text-sky-400 transition-colors underline decoration-dotted"
              title="Click to configure tariff"
            >
              TARIFF: {peso(electricityRate)} / kWh
            </button>
            <span>·</span>
            <button
              onClick={onOpenSettings}
              className="hover:text-sky-400 transition-colors underline decoration-dotted"
              title="Click to configure budget cap"
            >
              CAP: {peso(monthlyBudget)} / mo
            </button>
          </div>
        </div>
      </div>

      {/* Right Controls: Sampling window, telemetry refresh, alerts */}
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {/* Quick Clickable Tariff/Budget Chip on Tablet/Laptop */}
        <button
          onClick={onOpenSettings}
          className="hidden sm:flex md:hidden xl:flex items-center gap-1 px-2.5 py-1 rounded bg-white/[0.02] hover:bg-white/[0.05] border border-white/5 text-[11px] font-mono text-slate-300 transition-colors"
          title="Configure Tariff & Hardware Cap"
        >
          <SlidersHorizontal className="w-3 h-3 text-sky-400" />
          <span>{peso(electricityRate)}/kWh</span>
        </button>

        {/* Time Window Selector (7D, 30D, MTD) */}
        <div className="flex items-center bg-black/40 border border-white/10 rounded-md p-0.5 font-mono text-xs">
          {[
            { id: "7d", label: "7D" },
            { id: "30d", label: "30D" },
            { id: "month", label: "MTD" },
          ].map((range) => (
            <button
              key={range.id}
              onClick={() => setDateRange && setDateRange(range.id)}
              className={`px-2 sm:px-2.5 py-0.5 sm:py-1 rounded text-[10px] sm:text-[11px] font-medium transition-colors ${
                dateRange === range.id
                  ? "bg-slate-700 text-sky-300 font-semibold shadow-inner"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>

        {/* Sync Telemetry Button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="h-7 sm:h-8 px-2 sm:px-2.5 rounded-md bg-white/[0.03] hover:bg-white/[0.06] border border-white/10 flex items-center gap-1.5 text-slate-300 hover:text-white transition-colors text-xs font-mono"
          title="Resample hardware telemetry"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-sky-400" : "text-slate-400"}`}
          />
          <span className="hidden sm:inline text-[10px] sm:text-[11px]">RESAMPLE</span>
        </button>

        {/* Telemetry Alert Log */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="w-7 sm:w-8 h-7 sm:h-8 rounded-md bg-white/[0.03] hover:bg-white/[0.06] border border-white/10 flex items-center justify-center text-slate-300 hover:text-white transition-colors relative"
            title="System Alert Log"
          >
            <Bell className="w-3.5 h-3.5 text-slate-400" />
            {notificationCount > 0 && (
              <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-amber-400" />
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-72 sm:w-80 rounded-lg bg-slate-900 border border-white/10 shadow-2xl p-3 z-50 text-xs font-mono">
              <div className="flex items-center justify-between pb-2 border-b border-white/10 mb-2.5">
                <span className="font-semibold text-slate-200 uppercase tracking-wider text-[11px]">
                  TELEMETRY DIRECTIVES
                </span>
                <span className="text-[10px] text-amber-400">2 PENDING</span>
              </div>
              <div className="space-y-2 text-[11px]">
                <div className="p-2 rounded bg-rose-500/10 border border-rose-500/20 text-slate-300">
                  <div className="font-bold text-rose-400 text-[10px] uppercase">
                    [WARN] BUDGET OVERRUN PROJECTED
                  </div>
                  Cycle trend exceeds ₱2,000 threshold by +₱650.
                </div>
                <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-slate-300">
                  <div className="font-bold text-amber-400 text-[10px] uppercase">
                    [OPT] WORKLOAD SHIFT AVAILABLE
                  </div>
                  Shift llama3:70b to 8b for lightweight queries.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
