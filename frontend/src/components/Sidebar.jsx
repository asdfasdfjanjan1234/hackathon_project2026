import { useState } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { NAV_GROUPS } from "../navigation";
import Logo, { LogoMark } from "./Logo";
import ThemeToggle from "./ThemeToggle";

export default function Sidebar({
  activeTab = "dashboard",
  setActiveTab,
  mobileOpen = false,
  setMobileOpen,
  badges = {},
  liveReading,
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
          className="fixed inset-0 bg-ink/30 backdrop-blur-[2px] z-40 md:hidden"
          onClick={() => setMobileOpen && setMobileOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 flex flex-col bg-surface border-r border-line transition-all duration-200 ease-in-out shrink-0 ${
          mobileOpen ? "translate-x-0 w-64 shadow-pop" : "-translate-x-full md:translate-x-0"
        } ${collapsed ? "md:w-16" : "md:w-60"}`}
      >
        {/* Brand */}
        <div
          className={`h-16 flex items-center border-b border-line transition-all ${
            collapsed ? "justify-center px-2" : "justify-between px-4"
          }`}
        >
          <div className="flex items-center min-w-0 w-full">
            {expanded ? (
              <Logo />
            ) : (
              <div className="w-10 h-10 flex items-center justify-center">
                <LogoMark title="Kilo What?" className="h-9 w-9" />
              </div>
            )}
          </div>

          {/* Mobile Close Button */}
          {mobileOpen && (
            <button
              onClick={() => setMobileOpen && setMobileOpen(false)}
              className="md:hidden btn-icon"
              aria-label="Close navigation"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation Groups */}
        <nav className="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
          {NAV_GROUPS.map((group, gi) => (
            <div key={group.label} className="space-y-0.5">
              {expanded ? (
                <div className="text-xs font-medium text-ink-muted px-2.5 mb-1.5">{group.label}</div>
              ) : (
                gi > 0 && <div className="mx-2 mb-3 border-t border-line" />
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
                    aria-label={!expanded ? item.label : undefined}
                    className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm transition-colors group relative ${
                      isActive ? "bg-accent/10 text-accent font-semibold" : "text-ink-soft hover:text-ink hover:bg-sunken"
                    } ${!expanded ? "justify-center" : ""}`}
                  >
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-accent" : "text-ink-muted group-hover:text-ink-soft"}`} />
                    {expanded && <span className="flex-1 text-left truncate">{item.label}</span>}
                    {expanded && badge > 0 && (
                      <span className="min-w-[1.25rem] px-1.5 text-[11px] font-semibold leading-5 rounded-full bg-warn/15 text-warn tabular-nums">
                        {badge}
                      </span>
                    )}
                    {!expanded && badge > 0 && (
                      <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-warn" />
                    )}
                    {!expanded && (
                      <div className="absolute left-full ml-2 px-2 py-1 rounded-md bg-ink text-canvas text-xs whitespace-nowrap shadow-pop opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 pointer-events-none transition-opacity z-50">
                        {item.label}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Theme, in the drawer on phones (the header has it on wider screens) */}
        {mobileOpen && (
          <div className="px-3 pb-3 sm:hidden">
            <div className="text-xs font-medium text-ink-muted px-2.5 mb-1.5">Theme</div>
            <ThemeToggle showLabels />
          </div>
        )}

        {/* Power source status */}
        <div className="p-3 border-t border-line">
          <div className={`inset-panel p-2.5 flex items-center gap-2.5 ${!expanded ? "justify-center" : ""}`}>
            <span
              className={`h-2 w-2 rounded-full shrink-0 ${
                !liveReading ? "bg-ink-muted" : liveReading.estimated ? "bg-warn" : "bg-pos"
              }`}
            />
            {expanded && (
              <div className="flex-1 min-w-0 text-xs">
                <div className="flex items-center justify-between font-semibold text-ink">
                  <span>Power source</span>
                  <span className={liveReading?.estimated ? "text-warn" : "text-pos"}>
                    {liveReading?.estimated ? "Estimated" : liveReading ? "Measured" : "—"}
                  </span>
                </div>
                <div className="text-ink-muted truncate mt-0.5" title={sensor}>
                  {sensor} · this device
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Desktop Collapse Toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden md:flex h-10 items-center justify-center gap-1.5 text-xs text-ink-muted hover:text-ink hover:bg-sunken transition-colors border-t border-line"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <>
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </aside>
    </>
  );
}
