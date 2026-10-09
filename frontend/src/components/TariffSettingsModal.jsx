import { useEffect, useState } from "react";
import { X, RotateCcw, Check } from "lucide-react";
import { peso } from "../format";

// One setting: a slider for quick changes plus a number box for any exact value,
// so bills and rates outside the slider's range still work.
function Field({ label, value, onChange, min, max, step, format, accent, hint, children }) {
  return (
    <div className="p-4 inset-panel space-y-2.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-ink">{label}</span>
        <span className={`font-semibold text-sm tabular-nums ${accent}`}>{format(value)}</span>
      </div>
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={min}
          max={Math.max(max, value || 0)}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="flex-1 accent-accent cursor-pointer"
          aria-label={`${label} slider`}
        />
        <input
          type="number"
          min={0}
          step={step}
          value={value}
          onChange={(e) => onChange(e.target.value === "" ? 0 : parseFloat(e.target.value))}
          className="field-input w-24"
          aria-label={label}
        />
      </div>
      {hint && <div className="text-xs text-ink-muted leading-snug">{hint}</div>}
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
  currentCarbonBudget,
  currentTariff,
  currentPeakRate,
  currentOffpeakRate,
  defaults,
  onSave,
}) {
  const [rate, setRate] = useState(currentRate ?? 12);
  const [budget, setBudget] = useState(currentBudget ?? 2000);
  const [baseline, setBaseline] = useState(currentBaseline ?? 1500);
  const [bill, setBill] = useState(currentBill ?? 2500);
  const [cycleDay, setCycleDay] = useState(currentCycleStartDay ?? 1);
  const [carbonBudget, setCarbonBudget] = useState(currentCarbonBudget ?? 10);
  const [tariff, setTariff] = useState(currentTariff ?? "flat");
  const [peakRate, setPeakRate] = useState(currentPeakRate ?? 13.59);
  const [offpeakRate, setOffpeakRate] = useState(currentOffpeakRate ?? 9.86);

  // Start from the values in use each time the modal opens.
  useEffect(() => {
    if (!isOpen) return;
    setRate(currentRate ?? 12);
    setBudget(currentBudget ?? 2000);
    setBaseline(currentBaseline ?? 1500);
    setBill(currentBill ?? 2500);
    setCycleDay(currentCycleStartDay ?? 1);
    setCarbonBudget(currentCarbonBudget ?? 10);
    setTariff(currentTariff ?? "flat");
    setPeakRate(currentPeakRate ?? 13.59);
    setOffpeakRate(currentOffpeakRate ?? 9.86);
  }, [isOpen, currentRate, currentBudget, currentBaseline, currentBill, currentCycleStartDay, currentCarbonBudget,
      currentTariff, currentPeakRate, currentOffpeakRate]);

  // Escape closes without saving.
  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Back to the backend's .env values.
  const handleReset = () => {
    if (!defaults) return;
    setRate(defaults.rate);
    setBudget(defaults.budget);
    setBaseline(defaults.baseline);
    setBill(defaults.currentBill);
    setCycleDay(defaults.cycleStartDay);
    setCarbonBudget(defaults.carbonBudget);
    setTariff(defaults.tariff);
    setPeakRate(defaults.peakRate);
    setOffpeakRate(defaults.offpeakRate);
  };

  const handleApply = () => {
    if (onSave) {
      onSave({
        rate: Number(rate) || 0,
        budget: Number(budget) || 0,
        baseline: Number(baseline) || 0,
        currentBill: Number(bill) || 0,
        cycleStartDay: Math.min(Math.max(Math.round(Number(cycleDay)) || 1, 1), 31),
        carbonBudget: Number(carbonBudget) || 0,
        tariff,
        peakRate: Number(peakRate) || 0,
        offpeakRate: Number(offpeakRate) || 0,
      });
    }
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40 backdrop-blur-[2px]"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tariff-settings-title"
        className="relative w-full max-w-lg max-h-[calc(100vh-2rem)] overflow-y-auto rounded-2xl bg-surface border border-line shadow-pop p-6 space-y-5"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="tariff-settings-title" className="text-lg font-semibold text-ink">Your tariff & bill</h2>
            <div className="text-sm text-ink-muted mt-0.5">
              From your electricity bill. Every projection is recalculated with these values.
            </div>
          </div>
          <button onClick={onClose} className="btn-icon shrink-0" aria-label="Close settings" autoFocus>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <Field
            label="Rate (₱ per kWh)"
            value={rate}
            onChange={setRate}
            min={1}
            max={30}
            step={0.01}
            format={(v) => `${peso(v, 2)} / kWh`}
            accent="text-accent"
            hint="The total ₱/kWh on your bill (generation, transmission, distribution and taxes)."
          />
          <div className="p-4 inset-panel space-y-2.5">
            <div className="text-sm font-medium text-ink">Tariff</div>
            <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Tariff">
              {[
                ["flat", "Same rate all day", "Regular Meralco residential rate"],
                ["pop", "Peak / Off-Peak", "Meralco POP: cheaper 9 PM – 8 AM Mon–Sat and most of Sunday"],
              ].map(([id, title, hint]) => (
                <button
                  key={id}
                  role="radio"
                  aria-checked={tariff === id}
                  onClick={() => setTariff(id)}
                  className={`p-3 rounded-lg border text-left transition-colors ${
                    tariff === id
                      ? "border-accent bg-accent/[0.08] ring-1 ring-accent"
                      : "border-line bg-surface hover:border-line-strong"
                  }`}
                >
                  <div className={`font-medium text-sm ${tariff === id ? "text-accent" : "text-ink"}`}>{title}</div>
                  <div className="text-xs text-ink-muted mt-0.5 leading-snug">{hint}</div>
                </button>
              ))}
            </div>
            {tariff === "pop" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                {[
                  ["Peak ₱/kWh", peakRate, setPeakRate],
                  ["Off-peak ₱/kWh", offpeakRate, setOffpeakRate],
                ].map(([label, value, set]) => (
                  <label key={label} className="flex items-center justify-between gap-2 text-sm text-ink-soft">
                    <span>{label}</span>
                    <input
                      type="number"
                      min={0}
                      step={0.01}
                      value={value}
                      onChange={(e) => set(e.target.value === "" ? 0 : parseFloat(e.target.value))}
                      className="field-input w-24"
                    />
                  </label>
                ))}
                <div className="sm:col-span-2 text-xs text-ink-muted">
                  The all-in peak and off-peak rates on your POP bill. They change monthly with the generation charge.
                </div>
              </div>
            )}
          </div>
          <Field
            label="Monthly budget"
            value={budget}
            onChange={setBudget}
            min={0}
            max={20000}
            step={50}
            format={(v) => `${peso(v, 0)} / mo`}
            accent="text-warn"
          />
          <Field
            label="Bill before AI (baseline)"
            value={baseline}
            onChange={setBaseline}
            min={0}
            max={20000}
            step={50}
            format={(v) => peso(v, 0)}
            accent="text-ink"
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
            accent="text-ink"
            hint={'Used to answer "did AI raise my bill?": the increase over the baseline is split into rate change, AI and other usage.'}
          />
          <Field
            label="Monthly AI carbon budget"
            value={carbonBudget}
            onChange={setCarbonBudget}
            min={0}
            max={100}
            step={0.5}
            format={(v) => (v > 0 ? `${v} kg CO₂ / mo` : "Off")}
            accent="text-pos"
            hint="CO₂ from AI on this device plus cloud data centers. 0 turns the budget off."
          />
          <div className="p-4 inset-panel flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-ink">Billing cycle starts on day</div>
              <div className="text-xs text-ink-muted">The meter reading day on your bill (1–31).</div>
            </div>
            <input
              type="number"
              min={1}
              max={31}
              step={1}
              value={cycleDay}
              onChange={(e) => setCycleDay(e.target.value === "" ? "" : parseInt(e.target.value, 10))}
              className="field-input w-20"
              aria-label="Billing cycle start day"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-line gap-3">
          <button onClick={handleReset} disabled={!defaults} className="btn border-transparent">
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset defaults</span>
          </button>

          <div className="flex items-center gap-2">
            <button onClick={onClose} className="btn">
              Cancel
            </button>
            <button onClick={handleApply} className="btn-primary px-4">
              <Check className="w-3.5 h-3.5" />
              <span>Apply</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
