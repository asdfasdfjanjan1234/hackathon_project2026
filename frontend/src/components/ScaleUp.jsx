import { useState } from "react";
import { Calculator, Users } from "lucide-react";
import { peso, formatWatts, formatKwh } from "../format";

const DAYS_PER_MONTH = 30;

function Stepper({ label, value, setValue, min, max, unit }) {
  return (
    <label className="flex items-center justify-between gap-2 rounded-lg bg-surface border border-line px-3 py-2 focus-within:border-accent">
      <span className="text-xs font-medium text-ink-muted">{label}</span>
      <span className="flex items-center gap-1">
        <input
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(e) => setValue(Math.min(max, Math.max(min, Number(e.target.value) || min)))}
          className="w-14 bg-transparent text-right text-sm font-semibold text-ink focus:outline-none tabular-nums"
        />
        <span className="text-xs text-ink-muted">{unit}</span>
      </span>
    </label>
  );
}

function Line({ label, value, strong }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 border-b border-line last:border-0">
      <span className="text-xs text-ink-muted">{label}</span>
      <span className={`tabular-nums ${strong ? "text-accent font-semibold text-base" : "text-ink text-sm"}`}>
        {value}
      </span>
    </div>
  );
}

// "If you kept this up": the live AI draw as a monthly bill, and both scaled to a team of machines.
export default function ScaleUp({ liveReading, forecast, recs, rate }) {
  const [hours, setHours] = useState(4);
  const [machines, setMachines] = useState(1);

  const collecting = liveReading?.source === "collector";
  const aiWatts = collecting ? liveReading.ai_watts : null;
  const liveKwh = aiWatts != null ? (aiWatts * hours * DAYS_PER_MONTH) / 1000 : null;
  const liveCost = liveKwh != null ? liveKwh * rate : null;

  const nextMonth = forecast?.projections?.[0];
  const aiMonthly = nextMonth?.ai_cost ?? forecast?.ai_cost ?? 0;
  const savings = recs?.monthly_savings ?? 0;

  return (
    <section className="dash-card p-5 min-w-0">
      <div className="pb-4 border-b border-line min-w-0">
        <h2 className="card-title flex items-center gap-2">
          <Calculator className="w-4 h-4 text-ink-muted" /> If you kept this up
        </h2>
        <div className="card-sub mt-0.5">Today's AI draw as a monthly bill, for one machine or a team</div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <Stepper label="Use" value={hours} setValue={setHours} min={1} max={24} unit="h/day" />
        <Stepper label="Machines" value={machines} setValue={setMachines} min={1} max={500} unit="" />
      </div>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="inset-panel p-4 min-w-0">
          <div className="text-xs font-medium text-ink-soft mb-1">From the live reading</div>
          {aiWatts == null ? (
            <p className="text-xs text-ink-muted">Start the device reader (This Device) to project the AI apps running now.</p>
          ) : (
            <>
              <Line label="AI apps right now" value={formatWatts(aiWatts)} />
              <Line label={`${hours} h a day for a month`} value={formatKwh(liveKwh, 1)} />
              <Line label="Per machine" value={`${peso(liveCost)} / mo`} />
              <Line
                label={machines > 1 ? `${machines} machines` : "Per year"}
                value={machines > 1 ? `${peso(liveCost * machines)} / mo` : peso(liveCost * 12)}
                strong
              />
            </>
          )}
        </div>

        <div className="inset-panel p-4 min-w-0">
          <div className="text-xs font-medium text-ink-soft mb-1 flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5 text-ink-muted" /> From this cycle's forecast
          </div>
          <Line label="AI on the bill, next month" value={`${peso(aiMonthly * machines)} / mo`} />
          <Line label="Saved with recommendations" value={`${peso(savings * machines)} / mo`} />
          <Line label="Saved in a year" value={peso(savings * machines * 12)} strong />
        </div>
      </div>

      <p className="mt-3 text-xs text-ink-muted">
        Assumes every machine is used like this one. AI watts are this device's{" "}
        {liveReading?.estimated ? "estimated" : "measured"} power, split per app by CPU and GPU share.
      </p>
    </section>
  );
}
