import { useState } from "react";
import {
  Sliders,
  AlertOctagon,
  ArrowRightLeft,
  CheckCircle2,
  Loader2,
  Zap,
} from "lucide-react";
import { api } from "../api/client";
import { peso, formatWh, formatWatts, formatCo2 } from "../format";
import Figures from "./Figures";

const keyOf = (rec) => `${rec.rule}|${rec.model}`;

export default function Recommendations({ recs, liveReading, onApplied }) {
  // Advice the user has marked as done by hand (it can't be applied from here).
  const [markedDone, setMarkedDone] = useState({});
  // Recommendations applied to Ollama: {key: {busy, done, error, beforeWatts}}.
  const [applied, setApplied] = useState({});

  const recommendationsList = recs?.recommendations || [];
  // Combined by the backend: savings on the same model compound, and alternatives aren't added.
  const totalPotentialSavings = recs?.monthly_savings ?? 0;
  const aiWattsNow = liveReading?.source === "collector" ? liveReading.ai_watts : null;

  const toggleDone = (rec) => setMarkedDone((prev) => ({ ...prev, [keyOf(rec)]: !prev[keyOf(rec)] }));

  const applyNow = async (rec) => {
    const key = keyOf(rec);
    setApplied((prev) => ({ ...prev, [key]: { busy: true, beforeWatts: aiWattsNow } }));
    try {
      const res = await api.applyRecommendation(rec);
      setApplied((prev) => ({ ...prev, [key]: { ...prev[key], busy: false, done: res.done } }));
      onApplied?.();
    } catch (e) {
      setApplied((prev) => ({ ...prev, [key]: { ...prev[key], busy: false, error: e.message } }));
    }
  };

  const getActionConfig = (action) => {
    switch (action.toUpperCase()) {
      case "STOP":
        return { icon: AlertOctagon, tag: "tech-tag-alert", code: "Directive: stop" };
      case "SWITCH":
        return { icon: ArrowRightLeft, tag: "tech-tag-sim", code: "Directive: shift" };
      case "REDUCE":
      default:
        return { icon: Sliders, tag: "tech-tag-live", code: "Directive: throttle" };
    }
  };

  return (
    <section className="dash-card p-5 flex flex-col justify-between min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-3">
        <div className="min-w-0">
          <h2 className="card-title">Load shedding & optimization directives</h2>
          <div className="card-sub mt-0.5">Rule-based hardware load governance to remain within target budget cap</div>
        </div>

        <div className="text-right shrink-0">
          <div className="text-xs text-ink-muted">Recoverable tariff</div>
          <div className="text-lg font-bold text-pos tabular-nums leading-tight">
            {peso(totalPotentialSavings)} / mo
          </div>
          {recs?.monthly_co2_saved_kg > 0 && (
            <div className="text-xs text-pos tabular-nums">-{formatCo2(recs.monthly_co2_saved_kg)}</div>
          )}
        </div>
      </div>

      {/* Directives List */}
      <div className="divide-y divide-line">
        {recommendationsList.length === 0 ? (
          <div className="p-8 text-center text-ink-muted text-sm">
            No load shedding directives active. System operating within nominal parameters.
          </div>
        ) : (
          recommendationsList.map((rec) => {
            const config = getActionConfig(rec.action);
            const Icon = config.icon;
            const result = applied[keyOf(rec)];
            const isApplied = !!result?.done || !!markedDone[keyOf(rec)];

            return (
              <div
                key={keyOf(rec)}
                className={`py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-opacity ${
                  isApplied ? "opacity-70" : ""
                }`}
              >
                {/* Left: Code, Model & Message */}
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`tech-tag ${config.tag}`}>
                      <Icon className="w-3 h-3" />
                      {config.code}
                    </span>
                    <span className="text-sm font-bold text-ink truncate">{rec.model}</span>
                  </div>
                  <p className="text-sm text-ink-soft leading-relaxed">
                    <Figures text={rec.message} />
                  </p>
                  {result?.done && (
                    <p className="text-xs text-pos flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 shrink-0" />
                      <span>
                        {result.done}
                        {result.beforeWatts != null && aiWattsNow != null &&
                          ` AI draw: ${formatWatts(result.beforeWatts)} before → ${formatWatts(aiWattsNow)} now.`}
                      </span>
                    </p>
                  )}
                  {result?.error && <p className="text-xs text-neg">{result.error}</p>}
                </div>

                {/* Right: Recoverable Tariff & Button */}
                <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0">
                  <div className="text-right">
                    <span className="text-xs text-ink-muted block">
                      {rec.scope === "datacenter"
                        ? "Data center · not on bill"
                        : rec.scope === "carbon"
                        ? "CO₂ only · bill unchanged"
                        : rec.alternative
                        ? "Alternative"
                        : rec.rule === "budget" && !rec.monthly_savings
                        ? "Budget alert"
                        : "Recoverable"}
                    </span>
                    <span className="text-sm font-bold text-ink tabular-nums">
                      {rec.scope === "datacenter"
                        ? `-${formatWh(rec.wh_saved)} / mo`
                        : rec.scope === "carbon"
                        ? `-${formatCo2(rec.co2_saved_kg)} / mo`
                        : rec.rule === "budget" && !rec.monthly_savings
                        ? "—"
                        : `-${peso(rec.monthly_savings)} / mo`}
                    </span>
                    {rec.co2_saved_kg > 0 && rec.scope !== "carbon" && (
                      <span className="text-xs text-pos tabular-nums block">-{formatCo2(rec.co2_saved_kg)} / mo</span>
                    )}
                    {rec.co2_shifted_kg > 0 && (
                      <span className="text-xs text-ink-muted tabular-nums block" title="Moves CO₂ to the data center's grid; doesn't avoid it">
                        {formatCo2(rec.co2_shifted_kg)} shifted
                      </span>
                    )}
                  </div>

                  {rec.apply && !result?.done ? (
                    <button
                      onClick={() => applyNow(rec)}
                      disabled={result?.busy}
                      title={rec.apply.label}
                      className="btn-primary shrink-0"
                    >
                      {result?.busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                      <span>{rec.apply.kind === "switch" ? "Switch now" : "Unload now"}</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => !result?.done && toggleDone(rec)}
                      aria-pressed={isApplied}
                      className={`btn shrink-0 ${isApplied ? "border-pos/30 bg-pos/10 text-pos hover:bg-pos/15 hover:text-pos" : ""}`}
                    >
                      {isApplied ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>{result?.done ? "Applied" : "Done"}</span>
                        </>
                      ) : (
                        <span>Mark done</span>
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="pt-3 border-t border-line flex flex-wrap items-center justify-between text-xs text-ink-muted gap-2">
        <span>
          Rules: budget · smaller model · quantization · idle loaded · cost per hour · tool runs · cloud · growth · clean hours
        </span>
        <span className="tabular-nums">
          {recs?.bill_with_recommendations != null && (
            <>
              This cycle with recs: <span className="font-semibold text-ink">{peso(recs.bill_with_recommendations)}</span>
            </>
          )}
        </span>
      </div>
    </section>
  );
}
