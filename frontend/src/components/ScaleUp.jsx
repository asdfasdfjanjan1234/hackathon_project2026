import { useState } from "react";
import { Calculator, Users } from "lucide-react";
import { peso, formatWatts, formatKwh } from "../format";

const DAYS_PER_MONTH = 30;

function Stepper({ label, value, setValue, min, max, unit }) {
  return (
    <label className="flex items-center justify-between gap-2 rounded bg-black/40 border border-white/10 px-2 py-1.5">
      <span className="text-[10px] font-mono uppercase text-slate-500">{label}</span>
      <span className="flex items-center gap-1">
        <input
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(e) => setValue(Math.min(max, Math.max(min, Number(e.target.value) || min)))}
          className="w-14 bg-transparent text-right text-sm font-mono text-white outline-none tabular-nums"
        />
        <span className="text-[11px] font-mono text-slate-400">{unit}</span>
      </span>
    </label>
  );
}

function Line({ label, value, strong }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 border-b border-white/[0.04] last:border-0">
      <span className="text-[11px] text-slate-400">{label}</span>
      <span className={`font-mono tabular-nums ${strong ? "text-sky-300 font-bold text-sm" : "text-slate-200 text-xs"}`}>
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
    <section className="dash-card p-4 sm:p-5 min-w-0">
      <div className="flex items-center gap-2 pb-3 border-b border-white/5 min-w-0">
        <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
          <Calculator className="w-3.5 h-3.5" />
        </div>
        <div className="min-w-0">
          <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider truncate">
            If You Kept This Up
          </h2>
          <div className="text-[10px] text-slate-400 truncate">Today's AI draw as a monthly bill, for one machine or a team</div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Stepper label="Use" value={hours} setValue={setHours} min={1} max={24} unit="h/day" />
        <Stepper label="Machines" value={machines} setValue={setMachines} min={1} max={500} unit="" />
      </div>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-lg bg-black/30 border border-white/5 p-3 min-w-0">
          <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-300 mb-1">From the live reading</div>
          {aiWatts == null ? (
            <p className="text-[11px] text-slate-400">Start the device reader (This Device) to project the AI apps running now.</p>
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

        <div className="rounded-lg bg-black/30 border border-white/5 p-3 min-w-0">
          <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-300 mb-1 flex items-center gap-1.5">
            <Users className="w-3 h-3 text-sky-400" /> From this cycle's forecast
          </div>
          <Line label="AI on the bill, next month" value={`${peso(aiMonthly * machines)} / mo`} />
          <Line label="Saved with recommendations" value={`${peso(savings * machines)} / mo`} />
          <Line label="Saved in a year" value={peso(savings * machines * 12)} strong />
        </div>
      </div>

      <p className="mt-3 text-[10px] text-slate-500">
        Assumes every machine is used like this one. AI watts are this device's{" "}
        {liveReading?.estimated ? "estimated" : "measured"} power, split per app by CPU and GPU share.
      </p>
    </section>
  );
}
