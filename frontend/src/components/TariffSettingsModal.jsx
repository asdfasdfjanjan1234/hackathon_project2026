import { useEffect, useState } from "react";
import { X, SlidersHorizontal, RotateCcw, Check } from "lucide-react";
import { peso } from "../format";

// One setting: a slider for quick changes plus a number box for any exact value,
// so bills and rates outside the slider's range still work.
function Field({ label, value, onChange, min, max, step, format, accent, hint, children }) {
  return (
    <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-slate-300 font-bold uppercase text-[11px]">{label}</span>
        <span className={`font-bold text-sm tabular-nums ${accent}`}>{format(value)}</span>
      </div>
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={min}
          max={Math.max(max, value || 0)}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="flex-1 accent-sky-400 cursor-pointer h-1.5 bg-slate-700 rounded-lg"
        />
        <input
          type="number"
          min={0}
          step={step}
          value={value}
          onChange={(e) => onChange(e.target.value === "" ? 0 : parseFloat(e.target.value))}
          className="w-24 px-2 py-1 rounded bg-slate-950 border border-white/10 text-right text-slate-100 tabular-nums"
          aria-label={label}
        />
      </div>
      {hint && <div className="text-[10px] text-slate-400 font-sans">{hint}</div>}
      {children}
    </div>
  );
}

export default function TariffSettingsModal({
  isOpen,
  onClose,
  currentRate,
  currentBudget,
  currentBaseline,
  currentBill,
  currentCycleStartDay,
  defaults,
  onSave,
}) {
  const [rate, setRate] = useState(currentRate ?? 12);
  const [budget, setBudget] = useState(currentBudget ?? 2000);
  const [baseline, setBaseline] = useState(currentBaseline ?? 1500);
  const [bill, setBill] = useState(currentBill ?? 2500);
  const [cycleDay, setCycleDay] = useState(currentCycleStartDay ?? 1);

  // Start from the values in use each time the modal opens.
  useEffect(() => {
    if (!isOpen) return;
    setRate(currentRate ?? 12);
    setBudget(currentBudget ?? 2000);
    setBaseline(currentBaseline ?? 1500);
    setBill(currentBill ?? 2500);
    setCycleDay(currentCycleStartDay ?? 1);
  }, [isOpen, currentRate, currentBudget, currentBaseline, currentBill, currentCycleStartDay]);

  if (!isOpen) return null;

  // Back to the backend's .env values.
  const handleReset = () => {
    if (!defaults) return;
    setRate(defaults.rate);
    setBudget(defaults.budget);
    setBaseline(defaults.baseline);
    setBill(defaults.currentBill);
    setCycleDay(defaults.cycleStartDay);
  };

  const handleApply = () => {
    if (onSave) {
      onSave({
        rate: Number(rate) || 0,
        budget: Number(budget) || 0,
        baseline: Number(baseline) || 0,
        currentBill: Number(bill) || 0,
        cycleStartDay: Math.min(Math.max(Math.round(Number(cycleDay)) || 1, 1), 31),
      });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm select-none font-mono">
      <div className="relative w-full max-w-lg max-h-[calc(100vh-2rem)] overflow-y-auto rounded-xl bg-slate-900 border border-white/10 shadow-2xl p-5 sm:p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/25 flex items-center justify-center text-sky-400">
              <SlidersHorizontal className="w-3.5 h-3.5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">Your Tariff & Bill</h2>
              <div className="text-[10px] text-slate-400 font-sans">
                From your electricity bill. Every projection is recalculated with these values.
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.04]">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3 text-xs">
          <Field
            label="Rate (₱ per kWh)"
            value={rate}
            onChange={setRate}
            min={1}
            max={30}
            step={0.01}
            format={(v) => `${peso(v, 2)} / kWh`}
            accent="text-sky-300"
            hint="The total ₱/kWh on your bill (generation, transmission, distribution and taxes)."
          />
          <Field
            label="Monthly budget"
            value={budget}
            onChange={setBudget}
            min={0}
            max={20000}
            step={50}
            format={(v) => `${peso(v, 0)} / mo`}
            accent="text-amber-400"
          />
          <Field
            label="Bill before AI (baseline)"
            value={baseline}
            onChange={setBaseline}
            min={0}
            max={20000}
            step={50}
            format={(v) => peso(v, 0)}
            accent="text-slate-200"
            hint="A typical month before you started using AI on this computer."
          />
          <Field
            label="This month's bill"
            value={bill}
            onChange={setBill}
            min={0}
            max={20000}
            step={50}
            format={(v) => peso(v, 0)}
            accent="text-rose-300"
            hint={'Used to answer "did AI raise my bill?": the increase over the baseline is split into rate change, AI and other usage.'}
          />
          <div className="p-3 rounded-lg bg-black/40 border border-white/5 flex items-center justify-between gap-3">
            <div>
              <div className="text-slate-300 font-bold uppercase text-[11px]">Billing cycle starts on day</div>
              <div className="text-[10px] text-slate-400 font-sans">The meter reading day on your bill (1–31).</div>
            </div>
            <input
              type="number"
              min={1}
              max={31}
              step={1}
              value={cycleDay}
              onChange={(e) => setCycleDay(e.target.value === "" ? "" : parseInt(e.target.value, 10))}
              className="w-20 px-2 py-1 rounded bg-slate-950 border border-white/10 text-right text-slate-100 tabular-nums"
              aria-label="Billing cycle start day"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-white/10 gap-3 text-xs">
          <button
            onClick={handleReset}
            disabled={!defaults}
            className="px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] disabled:opacity-50 text-slate-400 hover:text-white transition-colors flex items-center gap-1.5"
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
              <span>APPLY</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
