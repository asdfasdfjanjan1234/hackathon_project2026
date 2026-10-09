import { useMemo } from "react";
import {
  Gauge,
  Zap,
  DollarSign,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { peso, formatWatts, formatKwh, formatCo2, formatDuration, shortDate } from "../format";
import { Counter } from "../motion";
import { StatCard } from "./Card";

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
    <div className="dash-card p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 min-w-0">
      <p className="text-sm text-ink-soft leading-relaxed min-w-0">
        <span className="font-bold text-ink">Trajectory: </span>
        This cycle projects to <strong className={`font-bold tabular-nums ${forecastTone}`}>{peso(forecastBill)}</strong> vs{" "}
        <span className="font-medium text-ink tabular-nums">{peso(baselineBill)}</span> before AI
        {nextMonth && (
          <>
            {" "}· next month <strong className="font-bold text-ink tabular-nums">{peso(nextMonth.bill)}</strong>, or{" "}
            <strong className="font-bold text-pos tabular-nums">{peso(nextMonth.bill_with_recommendations)}</strong> with
            recommendations
          </>
        )}
        .
      </p>

      <div className="grid grid-cols-3 sm:flex sm:items-center gap-2 shrink-0">
        <Step label="Before AI" value={baselineBill} />
        <ArrowRight className="hidden sm:block w-4 h-4 text-ink-muted shrink-0" />
        <Step label="Current path" value={forecastBill} valueClass={forecastTone} />
        <ArrowRight className="hidden sm:block w-4 h-4 text-ink-muted shrink-0" />
        <Step label="With recs" value={optimizedBill} valueClass="text-pos" />
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

  const aiShare = forecastBill > 0 ? Math.round((aiCost / forecastBill) * 100) : 0;

  return (
    <div className="stagger grid grid-cols-1 sm:grid-cols-2 gap-4 min-w-0 h-full">
      <StatCard
        title="Active power draw"
        icon={Gauge}
        iconClass="text-accent"
        value={currentWatts}
        format={formatWatts}
        sub={
          !liveReading
            ? "Waiting for the first reading"
            : estimated
            ? "No whole-machine sensor: estimated from CPU/GPU load"
            : `Measured · ${collecting ? "device reader" : liveReading.source}`
        }
        foot={
          collecting
            ? `AI apps: ${formatWatts(liveReading.ai_watts)}${idle != null && currentWatts != null ? ` · ${formatWatts(Math.max(0, currentWatts - idle))} over idle` : ""}`
            : "Start the device reader for watts per AI app"
        }
        tag={!liveReading ? "Offline" : estimated ? "Estimated" : "Measured"}
        tagClass={estimated || !liveReading ? "tech-tag-sim" : "tech-tag-live"}
      />
      <StatCard
        title={`AI energy on bill (${windowShort})`}
        icon={Zap}
        iconClass="text-volt"
        value={totalKwh}
        format={(v) => formatKwh(v, 1)}
        sub={
          factors
            ? `≈ ${formatCo2(totalKwh * factors.co2_kg_per_kwh)} · ${formatDuration((totalKwh * 1000) / factors.aircon_watts)} of a ${factors.aircon_watts} W aircon`
            : `Avg ${formatKwh(totalKwh / windowDays, 2)} / day`
        }
        foot={`${usage?.by_model?.length || 0} AI runtimes · ${formatKwh(totalKwh / windowDays, 2)} / day`}
        tag="Measured"
      />
      <StatCard
        title="AI cost this cycle"
        icon={DollarSign}
        value={aiCost}
        format={peso}
        sub={`Part of the ${peso(forecastBill)} projected bill`}
        foot={`At ${peso(rate ?? usage?.rate_per_kwh)} / kWh`}
        tag={`${aiShare}% of bill`}
        tagClass={aiCost >= 1 ? "tech-tag-alert" : "tech-tag-neutral"}
      />
      <StatCard
        title="Cycle projection"
        icon={Calendar}
        value={forecastBill}
        format={peso}
        valueClass={forecastTone}
        sub={`${shortDate(forecast?.cycle?.start)} – ${shortDate(forecast?.cycle?.end)} · Budget ${peso(budget)}`}
        foot={potentialSavings > 0 ? `With recommendations: ${peso(optimizedBill)}` : "No savings found this cycle"}
        tag={isOverBudget ? `Over by ${peso(forecastBill - budget)}` : "In budget"}
        tagClass={isOverBudget ? "tech-tag-alert" : "tech-tag-pos"}
      />
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
      <span className="block text-xs text-ink-muted truncate">{label}</span>
      <span className={`block text-sm font-bold tabular-nums truncate ${valueClass}`}>
        <Counter value={value} format={peso} />
      </span>
    </div>
  );
}
