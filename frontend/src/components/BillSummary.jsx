import { useMemo } from "react";
import {
  Gauge,
  Zap,
  DollarSign,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { peso, formatWatts, formatKwh, formatCo2, formatDuration, shortDate } from "../format";

export default function BillSummary({ forecast, recs, liveReading, usage, rate }) {
  const currentWatts = liveReading?.watts;
  const estimated = liveReading?.estimated ?? false;
  const collecting = liveReading?.source === "collector";

  const totalKwh = useMemo(
    () => (usage?.by_model || []).filter((m) => m.source === "measured").reduce((sum, m) => sum + (m.kwh || 0), 0),
    [usage]
  );
  const windowDays = usage?.window_days || 30;
  const windowShort = usage?.window?.short || `${windowDays}D`;
  const factors = usage?.factors;

  const baselineBill = forecast.baseline_bill;
  const forecastBill = forecast.forecast_bill;
  const aiCost = forecast.ai_cost;
  const optimizedBill = forecast.forecast_bill_with_recommendations ?? recs?.bill_with_recommendations ?? forecastBill;
  const potentialSavings = Math.max(0, forecastBill - optimizedBill);
  const budget = forecast.budget;
  const isOverBudget = budget != null && forecastBill > budget;
  const nextMonth = forecast.projections?.[0];
  const idle = liveReading?.power_model?.idle_watts;

  const cards = [
    {
      code: "METRIC-01",
      title: "Active Power Draw",
      value: formatWatts(currentWatts),
      subtext: !liveReading
        ? "Waiting for the first reading"
        : estimated
        ? "No whole-machine sensor: estimated from CPU/GPU load"
        : `Measured · ${collecting ? "device reader" : liveReading.source}`,
      badge: !liveReading ? "OFFLINE" : estimated ? "ESTIMATED" : "HARDWARE SENSOR",
      badgeType: estimated || !liveReading ? "sim" : "live",
      icon: Gauge,
      delta: {
        text: collecting
          ? `AI apps: ${formatWatts(liveReading.ai_watts)}${idle != null && currentWatts != null ? ` · ${formatWatts(Math.max(0, currentWatts - idle))} over idle` : ""}`
          : "Start the device reader for watts per AI app",
      },
    },
    {
      code: "METRIC-02",
      title: `AI Energy on Bill (${windowShort})`,
      value: formatKwh(totalKwh, 1),
      subtext: factors
        ? `≈ ${formatCo2(totalKwh * factors.co2_kg_per_kwh)} · ${formatDuration((totalKwh * 1000) / factors.aircon_watts)} of a ${factors.aircon_watts} W aircon`
        : `Avg ${formatKwh(totalKwh / windowDays, 2)} / day`,
      badge: "INTEGRATED",
      badgeType: "neutral",
      icon: Zap,
      delta: { text: `${usage?.by_model?.length || 0} AI runtimes · ${formatKwh(totalKwh / windowDays, 2)} / day` },
    },
    {
      code: "METRIC-03",
      title: "Attributed AI Tariff",
      value: peso(aiCost),
      subtext: `${forecastBill > 0 ? Math.round((aiCost / forecastBill) * 100) : 0}% of this cycle's projected bill`,
      badge: `+${peso(aiCost)}`,
      badgeType: aiCost >= 1 ? "alert" : "neutral",
      icon: DollarSign,
      delta: { text: `${peso(rate ?? usage?.rate_per_kwh)} / kWh tariff` },
    },
    {
      code: "METRIC-04",
      title: "Cycle Projection",
      value: peso(forecastBill),
      subtext: `${shortDate(forecast.cycle?.start)} – ${shortDate(forecast.cycle?.end)} · Cap: ${peso(budget)}`,
      badge: isOverBudget ? `OVER BY +${peso(forecastBill - budget)}` : "IN BUDGET",
      badgeType: isOverBudget ? "alert" : "neutral",
      icon: Calendar,
      delta: {
        text: potentialSavings > 0 ? `With recommendations: ${peso(optimizedBill)}` : "No savings found this cycle",
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
            This cycle projects to <strong className="text-rose-400 tabular-nums">{peso(forecastBill)}</strong> vs{" "}
            <span className="text-slate-400 tabular-nums">{peso(baselineBill)}</span> base
            {nextMonth && (
              <>
                {" "}· next month <strong className="text-rose-300 tabular-nums">{peso(nextMonth.bill)}</strong>, or{" "}
                <strong className="text-sky-300 tabular-nums">{peso(nextMonth.bill_with_recommendations)}</strong> with
                recommendations
              </>
            )}
            .
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
            <span className="text-[8px] sm:text-[9px] text-rose-400 block uppercase truncate">Current path</span>
            <span className="text-rose-300 font-bold tabular-nums text-[11px] sm:text-xs">{peso(forecastBill)}</span>
          </div>

          <div className="hidden sm:flex text-slate-500">
            <ArrowRight className="w-3.5 h-3.5" />
          </div>

          <div className="px-2 py-1 rounded bg-sky-500/10 border border-sky-500/25 text-center sm:text-left">
            <span className="text-[8px] sm:text-[9px] text-sky-400 block uppercase truncate">With recs</span>
            <span className="text-sky-300 font-bold tabular-nums text-[11px] sm:text-xs">{peso(optimizedBill)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
