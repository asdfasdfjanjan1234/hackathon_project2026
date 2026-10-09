import { useMemo } from "react";
import {
  Gauge,
  Zap,
  DollarSign,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { peso, formatWatts, formatKwh, formatCo2, formatDuration, shortDate } from "../format";

const TAG_CLASS = {
  live: "tech-tag-live",
  sim: "tech-tag-sim",
  alert: "tech-tag-alert",
  pos: "tech-tag-pos",
  neutral: "tech-tag-neutral",
};

export function TrajectoryBanner({ forecast, recs }) {
  if (!forecast) return null;
  const baselineBill = forecast.baseline_bill;
  const forecastBill = forecast.forecast_bill;
  const optimizedBill = forecast.forecast_bill_with_recommendations ?? recs?.bill_with_recommendations ?? forecastBill;
  const budget = forecast.budget;
  const isOverBudget = budget != null && forecastBill > budget;
  const nextMonth = forecast.projections?.[0];
  const forecastTone = isOverBudget ? "text-neg" : "text-ink";

  return (
    <div className="dash-card p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4 min-w-0">
      <p className="text-sm text-ink-soft leading-relaxed min-w-0">
        <span className="font-medium text-ink">Trajectory: </span>
        This cycle projects to <strong className={`font-semibold tabular-nums ${forecastTone}`}>{peso(forecastBill)}</strong> vs{" "}
        <span className="tabular-nums">{peso(baselineBill)}</span> base
        {nextMonth && (
          <>
            {" "}· next month <strong className="font-semibold text-ink tabular-nums">{peso(nextMonth.bill)}</strong>, or{" "}
            <strong className="font-semibold text-pos tabular-nums">{peso(nextMonth.bill_with_recommendations)}</strong> with
            recommendations
          </>
        )}
        .
      </p>

      <div className="grid grid-cols-3 sm:flex sm:items-center gap-2 shrink-0">
        <Step label="Baseline" value={peso(baselineBill)} />
        <ArrowRight className="hidden sm:block w-4 h-4 text-ink-muted shrink-0" />
        <Step label="Current path" value={peso(forecastBill)} valueClass={forecastTone} />
        <ArrowRight className="hidden sm:block w-4 h-4 text-ink-muted shrink-0" />
        <Step label="With recs" value={peso(optimizedBill)} valueClass="text-pos" />
      </div>
    </div>
  );
}

export function BillMetricsGrid({ forecast, recs, liveReading, usage, rate }) {
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

  const baselineBill = forecast?.baseline_bill;
  const forecastBill = forecast?.forecast_bill;
  const aiCost = forecast?.ai_cost ?? 0;
  const optimizedBill = forecast?.forecast_bill_with_recommendations ?? recs?.bill_with_recommendations ?? forecastBill;
  const potentialSavings = Math.max(0, (forecastBill ?? 0) - (optimizedBill ?? 0));
  const budget = forecast?.budget;
  const isOverBudget = budget != null && forecastBill > budget;
  const idle = liveReading?.power_model?.idle_watts;
  const forecastTone = isOverBudget ? "text-neg" : "text-ink";

  const cards = [
    {
      title: "Active power draw",
      value: formatWatts(currentWatts),
      subtext: !liveReading
        ? "Waiting for the first reading"
        : estimated
        ? "No whole-machine sensor: estimated from CPU/GPU load"
        : `Measured · ${collecting ? "device reader" : liveReading.source}`,
      badge: !liveReading ? "Offline" : estimated ? "Estimated" : "Hardware sensor",
      badgeType: estimated || !liveReading ? "sim" : "live",
      icon: Gauge,
      delta: {
        text: collecting
          ? `AI apps: ${formatWatts(liveReading.ai_watts)}${idle != null && currentWatts != null ? ` · ${formatWatts(Math.max(0, currentWatts - idle))} over idle` : ""}`
          : "Start the device reader for watts per AI app",
      },
    },
    {
      title: `AI energy on bill (${windowShort})`,
      value: formatKwh(totalKwh, 1),
      subtext: factors
        ? `≈ ${formatCo2(totalKwh * factors.co2_kg_per_kwh)} · ${formatDuration((totalKwh * 1000) / factors.aircon_watts)} of a ${factors.aircon_watts} W aircon`
        : `Avg ${formatKwh(totalKwh / windowDays, 2)} / day`,
      badge: "Integrated",
      badgeType: "neutral",
      icon: Zap,
      delta: { text: `${usage?.by_model?.length || 0} AI runtimes · ${formatKwh(totalKwh / windowDays, 2)} / day` },
    },
    {
      title: "Attributed AI tariff",
      value: peso(aiCost),
      subtext: `${forecastBill > 0 ? Math.round((aiCost / forecastBill) * 100) : 0}% of this cycle's projected bill`,
      badge: `+${peso(aiCost)}`,
      badgeType: aiCost >= 1 ? "alert" : "neutral",
      icon: DollarSign,
      delta: { text: `${peso(rate ?? usage?.rate_per_kwh)} / kWh tariff` },
    },
    {
      title: "Cycle projection",
      value: peso(forecastBill),
      valueClass: forecastTone,
      subtext: `${shortDate(forecast?.cycle?.start)} – ${shortDate(forecast?.cycle?.end)} · Cap: ${peso(budget)}`,
      badge: isOverBudget ? `Over by +${peso(forecastBill - budget)}` : "In budget",
      badgeType: isOverBudget ? "alert" : "pos",
      icon: Calendar,
      delta: {
        text: potentialSavings > 0 ? `With recommendations: ${peso(optimizedBill)}` : "No savings found this cycle",
      },
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 min-w-0 h-full">
      {cards.map((card, i) => {
        const Icon = card.icon;
        return (
          <div key={i} className="stat-card flex flex-col justify-between min-w-0 h-full">
            <div>
              <div className="flex items-center justify-between gap-2 mb-3">
                <span className="eyebrow">{card.title}</span>
                <Icon className="w-4 h-4 text-ink-muted shrink-0" />
              </div>
              <div className={`text-[28px] leading-none font-semibold tracking-tight tabular-nums truncate ${card.valueClass || "text-ink"}`}>
                {card.value}
              </div>
              <div className="text-xs text-ink-muted mt-2 leading-snug">{card.subtext}</div>
            </div>

            <div className="mt-4 pt-3 border-t border-line flex items-center justify-between gap-2">
              <span className="text-xs text-ink-soft truncate" title={card.delta.text}>
                {card.delta.text}
              </span>
              <span className={`tech-tag shrink-0 ${TAG_CLASS[card.badgeType]}`}>{card.badge}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function BillSummary(props) {
  return (
    <div className="space-y-4 min-w-0">
      <TrajectoryBanner forecast={props.forecast} recs={props.recs} />
      <BillMetricsGrid {...props} />
    </div>
  );
}

function Step({ label, value, valueClass = "text-ink" }) {
  return (
    <div className="inset-panel px-3 py-1.5 min-w-0">
      <span className="block text-[11px] text-ink-muted truncate">{label}</span>
      <span className={`block text-sm font-semibold tabular-nums truncate ${valueClass}`}>{value}</span>
    </div>
  );
}
