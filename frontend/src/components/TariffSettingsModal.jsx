import { useState } from "react";
import { X, SlidersHorizontal, RotateCcw, Check, Zap } from "lucide-react";
import { peso } from "../format";

export default function TariffSettingsModal({
  isOpen,
  onClose,
  currentRate,
  currentBudget,
  currentBaseline,
  onSave,
}) {
  const [rate, setRate] = useState(currentRate || 12.0);
  const [budget, setBudget] = useState(currentBudget || 2000);
  const [baseline, setBaseline] = useState(currentBaseline || 1500);

  if (!isOpen) return null;

  const handleReset = () => {
    setRate(12.0);
    setBudget(2000);
    setBaseline(1500);
  };

  const handleApply = () => {
    if (onSave) {
      onSave({
        rate: Number(rate),
        budget: Number(budget),
        baseline: Number(baseline),
      });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm select-none font-mono">
      <div className="relative w-full max-w-lg rounded-xl bg-slate-900 border border-white/10 shadow-2xl p-5 sm:p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/25 flex items-center justify-center text-sky-400">
              <SlidersHorizontal className="w-3.5 h-3.5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Tariff & Grid Hardware Parameters
              </h2>
              <div className="text-[10px] text-slate-400 font-sans">
                Real-time dynamic recalculation of billing projections & thresholds
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.04]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Sliders Form */}
        <div className="space-y-4 text-xs">
          {/* 1. Electricity Rate */}
          <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-bold uppercase text-[11px]">
                GRID TARIFF RATE (₱/kWh)
              </span>
              <span className="text-sky-300 font-bold text-sm tabular-nums">
                {peso(rate, 2)} / kWh
              </span>
            </div>
            <input
              type="range"
              min="6"
              max="28"
              step="0.5"
              value={rate}
              onChange={(e) => setRate(parseFloat(e.target.value))}
              className="w-full accent-sky-400 cursor-pointer h-1.5 bg-slate-700 rounded-lg"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>₱6.00 (Provincial)</span>
              <span>₱12.00 (Meralco Avg)</span>
              <span>₱28.00 (Peak Commercial)</span>
            </div>
          </div>

          {/* 2. Monthly Budget Cap */}
          <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-bold uppercase text-[11px]">
                MONTHLY BUDGET TARGET CAP
              </span>
              <span className="text-amber-400 font-bold text-sm tabular-nums">
                {peso(budget, 0)} / mo
              </span>
            </div>
            <input
              type="range"
              min="1000"
              max="6000"
              step="100"
              value={budget}
              onChange={(e) => setBudget(parseFloat(e.target.value))}
              className="w-full accent-amber-400 cursor-pointer h-1.5 bg-slate-700 rounded-lg"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>₱1,000</span>
              <span>₱2,000 (Target)</span>
              <span>₱6,000 (Unconstrained)</span>
            </div>
          </div>

          {/* 3. Non-AI Baseline Bill */}
          <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-bold uppercase text-[11px]">
                BASELINE BILL (NON-AI HOUSEHOLD)
              </span>
              <span className="text-slate-200 font-bold text-sm tabular-nums">
                {peso(baseline, 0)}
              </span>
            </div>
            <input
              type="range"
              min="500"
              max="4000"
              step="100"
              value={baseline}
              onChange={(e) => setBaseline(parseFloat(e.target.value))}
              className="w-full accent-slate-400 cursor-pointer h-1.5 bg-slate-700 rounded-lg"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>₱500</span>
              <span>₱1,500 (John's Pre-AI)</span>
              <span>₱4,000</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-white/10 gap-3 text-xs">
          <button
            onClick={handleReset}
            className="px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-slate-400 hover:text-white transition-colors flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>RESET DEFAULTS</span>
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-slate-300 hover:text-white transition-colors"
            >
              CANCEL
            </button>
            <button
              onClick={handleApply}
              className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <Check className="w-3.5 h-3.5" />
              <span>APPLY PARAMETERS</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
