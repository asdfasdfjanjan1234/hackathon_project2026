import { useState } from "react";
import {
  Sliders,
  AlertOctagon,
  ArrowRightLeft,
  CheckCircle2,
  Terminal,
} from "lucide-react";
import { peso, formatWh } from "../format";

export default function Recommendations({ recs, onApplyDirective }) {
  const [appliedActions, setAppliedActions] = useState({});

  const recommendationsList = recs?.recommendations || [];
  // Combined by the backend: savings on the same model compound, and alternatives aren't added.
  const totalPotentialSavings = recs?.monthly_savings ?? 0;

  const handleApply = (idx) => {
    const isNowApplied = !appliedActions[idx];
    setAppliedActions((prev) => ({
      ...prev,
      [idx]: isNowApplied,
    }));
    if (onApplyDirective) {
      onApplyDirective(recommendationsList[idx], isNowApplied);
    }
  };

  const getActionConfig = (action) => {
    switch (action.toUpperCase()) {
      case "STOP":
        return {
          icon: AlertOctagon,
          badgeColor: "bg-rose-500/10 text-rose-400 border-rose-500/25",
          buttonLabel: "EXECUTE TERMINATE",
          code: "DIRECTIVE: STOP",
        };
      case "SWITCH":
        return {
          icon: ArrowRightLeft,
          badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/25",
          buttonLabel: "APPLY RUNTIME SHIFT",
          code: "DIRECTIVE: SHIFT",
        };
      case "REDUCE":
      default:
        return {
          icon: Sliders,
          badgeColor: "bg-sky-500/10 text-sky-400 border-sky-500/25", // Precision Cyan, NO GREEN
          buttonLabel: "ENFORCE THROTTLE",
          code: "DIRECTIVE: THROTTLE",
        };
    }
  };

  return (
    <section className="dash-card p-4 sm:p-5 flex flex-col justify-between select-none font-mono min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-white/5 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <Sliders className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wider truncate">
              Load Shedding & Optimization Directives
            </h2>
            <div className="text-[10px] text-slate-400 font-sans truncate">
              Rule-based hardware load governance to remain within target budget cap
            </div>
          </div>
        </div>

        {/* Total Recoverable Pill (Cyan, NO GREEN) */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-sky-500/10 border border-sky-500/25 text-xs shrink-0">
          <span className="text-slate-300 text-[11px]">RECOVERABLE TARIFF:</span>
          <span className="text-sky-300 font-bold tabular-nums">
            {peso(totalPotentialSavings)} / mo
          </span>
        </div>
      </div>

      {/* Directives List */}
      <div className="space-y-2.5 my-3">
        {recommendationsList.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-xs">
            NO LOAD SHEDDING DIRECTIVES ACTIVE. SYSTEM OPERATING WITHIN NOMINAL PARAMETERS.
          </div>
        ) : (
          recommendationsList.map((rec, i) => {
            const config = getActionConfig(rec.action);
            const Icon = config.icon;
            const isApplied = !!appliedActions[i];

            return (
              <div
                key={i}
                className={`p-3 rounded border transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                  isApplied
                    ? "border-sky-500/35 bg-sky-950/20"
                    : "border-white/5 bg-black/30 hover:border-white/10"
                }`}
              >
                {/* Left: Code, Model & Message */}
                <div className="flex items-start gap-3 min-w-0">
                  <div className="mt-0.5 shrink-0">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider border ${config.badgeColor}`}
                    >
                      <Icon className="w-3 h-3" />
                      {config.code}
                    </span>
                  </div>

                  <div className="min-w-0">
                    <div className="text-xs font-bold text-slate-200 flex items-center gap-2">
                      <span className="text-sky-400 truncate">{rec.model}</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 font-sans leading-relaxed">
                      {rec.message}
                    </p>
                  </div>
                </div>

                {/* Right: Recoverable Tariff & Button */}
                <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-white/5">
                  <div className="text-right">
                    <span className="text-[9px] text-slate-400 uppercase tracking-wider block">
                      {rec.scope === "datacenter"
                        ? "DATA CENTER · NOT ON BILL"
                        : rec.alternative
                        ? "ALTERNATIVE"
                        : rec.rule === "budget" && !rec.monthly_savings
                        ? "BUDGET ALERT"
                        : "RECOVERABLE"}
                    </span>
                    <span className="text-xs font-bold text-sky-300 tabular-nums">
                      {rec.scope === "datacenter"
                        ? `-${formatWh(rec.wh_saved)} / mo`
                        : rec.rule === "budget" && !rec.monthly_savings
                        ? "—"
                        : `-${peso(rec.monthly_savings)} / mo`}
                    </span>
                  </div>

                  <button
                    onClick={() => handleApply(i)}
                    className={`px-3 py-1.5 rounded text-[11px] font-bold transition-colors flex items-center gap-1.5 shrink-0 border ${
                      isApplied
                        ? "bg-sky-600 text-white border-sky-500 shadow-sm"
                        : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border-white/10"
                    }`}
                  >
                    {isApplied ? (
                      <>
                        <CheckCircle2 className="w-3 h-3 text-sky-200" />
                        <span>COMMITTED</span>
                      </>
                    ) : (
                      <span>{config.buttonLabel}</span>
                    )}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="pt-2 border-t border-white/5 flex flex-wrap items-center justify-between text-[10px] text-slate-400 gap-2">
        <span>
          RULES: BUDGET · SMALLER MODEL · QUANTIZATION · IDLE LOADED · COST PER HOUR · TOOL RUNS · CLOUD · GROWTH
        </span>
        <span>
          {recs?.bill_with_recommendations != null && `THIS CYCLE WITH RECS: ${peso(recs.bill_with_recommendations)}`}
        </span>
      </div>
    </section>
  );
}
