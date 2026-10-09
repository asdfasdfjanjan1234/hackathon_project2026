import { useState } from "react";
import { ChevronLeft, ChevronRight, Zap, X } from "lucide-react";
import { NAV_GROUPS } from "../navigation";

export default function Sidebar({
  activeTab = "dashboard",
  setActiveTab,
  mobileOpen = false,
  setMobileOpen,
  badges = {},
  liveReading,
  dataSource,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const reading = liveReading?.source === "collector";
  const sensor = !liveReading ? "connecting…" : reading ? "device reader" : liveReading.source;

  const expanded = !collapsed || mobileOpen;

  const handleNavClick = (id) => {
    if (setActiveTab) setActiveTab(id);
    if (setMobileOpen) setMobileOpen(false);
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setMobileOpen && setMobileOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 flex flex-col bg-panelBg border-r border-white/5 transition-all duration-200 ease-in-out shrink-0 select-none ${
          mobileOpen ? "translate-x-0 w-64 shadow-2xl" : "-translate-x-full md:translate-x-0"
        } ${collapsed ? "md:w-16" : "md:w-60"}`}
      >
        {/* Technical Brand Header */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-white/5">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/25 flex items-center justify-center text-sky-400 shrink-0">
              <Zap className="w-4 h-4" />
            </div>
            {expanded && (
              <div className="flex flex-col overflow-hidden min-w-0">
                <div className="font-mono font-bold text-sm tracking-wider text-slate-100 flex items-center gap-1.5 whitespace-nowrap">
                  <span>WATT<span className="text-sky-400">TRACE</span></span>
                  <span className="text-[9px] font-mono font-semibold px-1 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    SCADA
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 truncate uppercase tracking-widest font-mono">
                  Hardware Telemetry
                </span>
              </div>
            )}
          </div>

          {/* Mobile Close Button */}
          {mobileOpen && (
            <button
              onClick={() => setMobileOpen && setMobileOpen(false)}
              className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.04]"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation Groups */}
        <nav className="flex-1 px-2.5 py-4 space-y-5 overflow-y-auto">
          {NAV_GROUPS.map((group, gi) => (
            <div key={group.label} className="space-y-1">
              {expanded ? (
                <div className="text-[10px] font-mono tracking-widest uppercase text-slate-500 px-2.5 mb-2">
                  {group.label}
                </div>
              ) : (
                gi > 0 && <div className="mx-2.5 mb-2 border-t border-white/5" />
              )}
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                const badge = badges[item.id];
                return (
                  <button
                    key={item.id}
                    onClick={() => handleNavClick(item.id)}
                    aria-current={isActive ? "page" : undefined}
                    className={`w-full flex items-center gap-3 px-2.5 py-2.5 rounded-lg text-xs font-medium transition-colors group relative ${
                      isActive
                        ? "bg-sky-500/10 text-sky-300 border border-sky-500/20 shadow-sm"
                        : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.03] border border-transparent"
                    }`}
                    title={!expanded ? item.label : undefined}
                  >
                    {isActive && (
                      <span className="absolute -left-2.5 top-1.5 bottom-1.5 w-0.5 rounded-r bg-sky-400" />
                    )}
                    <Icon
                      className={`w-4 h-4 shrink-0 ${
                        isActive ? "text-sky-400" : "text-slate-400 group-hover:text-slate-300"
                      }`}
                    />
                    {expanded && <span className="flex-1 text-left truncate font-sans">{item.label}</span>}
                    {expanded && badge > 0 && (
                      <span className="px-1.5 py-0.2 text-[9px] font-mono font-bold rounded bg-amber-500/10 text-amber-400 border border-amber-500/25">
                        {badge}
                      </span>
                    )}
                    {!expanded && badge > 0 && (
                      <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-amber-400" />
                    )}
                    {!expanded && (
                      <div className="absolute left-full ml-2 px-2 py-1 rounded bg-slate-900 text-slate-200 text-xs font-mono whitespace-nowrap shadow-xl border border-white/10 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                        {item.label}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Hardware Sensor Bus Status (CYAN, NO GREEN) */}
        <div className="p-2.5 border-t border-white/5">
          <div
            className={`rounded-lg p-2.5 bg-black/40 border border-white/5 flex items-center gap-2.5 ${
              !expanded ? "justify-center" : ""
            }`}
          >
            {/* Precision Instrument Cyan Pulsing Indicator */}
            <div className="relative shrink-0">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-60"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-400"></span>
              </span>
            </div>
            {expanded && (
              <div className="flex-1 min-w-0 font-mono text-[10px]">
                <div className="flex items-center justify-between text-slate-300 font-semibold">
                  <span>POWER SOURCE</span>
                  <span className={liveReading?.estimated ? "text-amber-300" : "text-sky-400"}>
                    {liveReading?.estimated ? "ESTIMATED" : liveReading ? "MEASURED" : "—"}
                  </span>
                </div>
                <div className="text-slate-400 truncate mt-0.5" title={sensor}>
                  {sensor} · {dataSource === "device" ? "this device" : "sample data"}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Desktop Collapse Toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden md:flex h-9 items-center justify-center text-slate-400 hover:text-white hover:bg-white/[0.03] transition-colors border-t border-white/5"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>COLLAPSE</span>
            </div>
          )}
        </button>
      </aside>
    </>
  );
}
