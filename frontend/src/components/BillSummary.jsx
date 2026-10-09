import { useMemo } from "react";
import {
  Gauge,
  Zap,
  DollarSign,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { peso, formatWatts, formatKwh } from "../format";

export default function BillSummary({ forecast, recs, liveReading, usage }) {
  const currentWatts = liveReading?.watts ?? 48.5;
  const isSimulated = liveReading?.simulated ?? false;

  const totalKwh = useMemo(() => {
    if (!usage?.by_model) return 76.0;
    return usage.by_model.reduce((sum, m) => sum + (m.kwh || 0), 0);
  }, [usage]);

  const baselineBill = forecast?.baseline_bill || 1500;
  const forecastBill = forecast?.forecast_bill || 2650;
  const aiCost = forecast?.ai_cost || (forecastBill - baselineBill);
  const optimizedBill = recs?.bill_with_recommendations || (forecastBill - 520);
  const potentialSavings = Math.max(0, forecastBill - optimizedBill);

  const budget = 2000;
  const isOverBudget = forecastBill > budget;

  const cards = [
    {
      code: "METRIC-01",
      title: "Active Power Draw",
      value: formatWatts(currentWatts),
      subtext: isSimulated ? "Simulated telemetry stream" : "Hardware sensor (Apple Silicon)",
      badge: isSimulated ? "SIMULATED" : "HARDWARE SENSOR",
      badgeType: isSimulated ? "sim" : "live", // Cyan in App.css, no green
      icon: Gauge,
      delta: { text: "+33.5 W over idle", isPositive: false },
    },
    {
      code: "METRIC-02",
      title: "Integrated Energy (30D)",
      value: formatKwh(totalKwh, 1),
      subtext: `Avg burn: ~${(totalKwh / 30).toFixed(2)} kWh / day`,
      badge: "INTEGRATED",
      badgeType: "neutral",
      icon: Zap,
      delta: { text: "4 active runtimes", isPositive: true },
    },
    {
      code: "METRIC-03",
      title: "Attributed AI Tariff",
      value: peso(aiCost),
      subtext: `${Math.round((aiCost / forecastBill) * 100)}% of total monthly billing`,
      badge: `+${peso(aiCost)}`,
      badgeType: "alert",
      icon: DollarSign,
      delta: { text: "₱12.00 / kWh tariff", isPositive: false },
    },
    {
      code: "METRIC-04",
      title: "Cycle Projection (EOM)",
      value: peso(forecastBill),
      subtext: `Target Cap: ${peso(budget)}`,
      badge: isOverBudget ? `OVER BY +${peso(forecastBill - budget)}` : "IN BUDGET",
      badgeType: isOverBudget ? "alert" : "neutral", // Neutral monochrome, no green
      icon: Calendar,
      delta: {
        text: potentialSavings > 0 ? `Optimizable to ${peso(optimizedBill)}` : "Within bounds",
        isPositive: true,
      },
    },
  ];

  return (
    <div className="space-y-3 select-none min-w-0">
      {/* 4 Instrumentation Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 min-w-0">
        {cards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              className="stat-card flex flex-col justify-between min-w-0"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono tracking-wider uppercase text-slate-400 truncate">
                    {card.title}
                  </span>
                  <span className="text-[9px] font-mono text-slate-400 shrink-0 ml-1">
                    {card.code}
                  </span>
                </div>

                <div className="my-1">
                  <div className="text-2xl sm:text-3xl font-mono font-bold tracking-tight text-white tabular-nums truncate">
                    {card.value}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1 truncate">
                    {card.subtext}
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-2.5 border-t border-white/5 flex items-center justify-between text-xs font-mono gap-2">
                <span className="text-[10px] sm:text-[11px] text-slate-400 truncate">
                  {card.delta.text}
                </span>

                <span
                  className={`tech-tag shrink-0 ${
                    card.badgeType === "live"
                      ? "tech-tag-live"
                      : card.badgeType === "sim"
                      ? "tech-tag-sim"
                      : card.badgeType === "alert"
                      ? "tech-tag-alert"
                      : "tech-tag-neutral"
                  }`}
                >
                  {card.badge}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Industrial Pipeline Trajectory Banner (Fully Responsive on Mobile) */}
      <div className="p-3 sm:p-3.5 rounded-lg bg-black/40 border border-white/10 flex flex-col md:flex-row md:items-center justify-between gap-3 font-mono text-xs min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold shrink-0">
            TRAJECTORY:
          </span>
          <span className="text-slate-300 text-[11px] sm:text-xs truncate">
            Unregulated projects to <strong className="text-rose-400 tabular-nums">{peso(forecastBill)}</strong> vs{" "}
            <span className="text-slate-400 tabular-nums">{peso(baselineBill)}</span> base.
          </span>
        </div>

        {/* 3 Step Ribbon - Wraps gracefully on mobile */}
        <div className="grid grid-cols-3 sm:flex sm:items-center gap-1.5 sm:gap-2.5 text-xs shrink-0">
          <div className="px-2 py-1 rounded bg-white/[0.04] border border-white/10 text-center sm:text-left">
            <span className="text-[8px] sm:text-[9px] text-slate-400 block uppercase truncate">Baseline</span>
            <span className="text-slate-200 font-bold tabular-nums text-[11px] sm:text-xs">{peso(baselineBill)}</span>
          </div>

          <div className="hidden sm:flex text-slate-500">
            <ArrowRight className="w-3.5 h-3.5" />
          </div>

          <div className="px-2 py-1 rounded bg-rose-500/10 border border-rose-500/25 text-center sm:text-left">
            <span className="text-[8px] sm:text-[9px] text-rose-400 block uppercase truncate">Unregulated</span>
            <span className="text-rose-300 font-bold tabular-nums text-[11px] sm:text-xs">{peso(forecastBill)}</span>
          </div>

          <div className="hidden sm:flex text-slate-500">
            <ArrowRight className="w-3.5 h-3.5" />
          </div>

          <div className="px-2 py-1 rounded bg-sky-500/10 border border-sky-500/25 text-center sm:text-left">
            <span className="text-[8px] sm:text-[9px] text-sky-400 block uppercase truncate">Optimized</span>
            <span className="text-sky-300 font-bold tabular-nums text-[11px] sm:text-xs">{peso(optimizedBill)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
