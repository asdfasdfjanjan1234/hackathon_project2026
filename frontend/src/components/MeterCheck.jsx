import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Plug, Trash2, Timer, Gauge, Loader2 } from "lucide-react";
import { formatWatts, formatKwh } from "../format";

// How close our whole-machine reading is to a plug-in power meter at the wall.
const diffColor = (pct) => {
  const a = Math.abs(pct);
  if (a <= 10) return "text-sky-300";
  if (a <= 20) return "text-amber-300";
  return "text-rose-300";
};

const signed = (pct) => `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;

const timeOf = (ts) =>
  new Date(ts * 1000).toLocaleTimeString("en-PH", { hour: "numeric", minute: "2-digit" });

function NumberForm({ label, unit, button, busy, onSubmit, step = "any" }) {
  const [value, setValue] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (value === "") return;
    if (await onSubmit(Number(value))) setValue("");
  };
  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <label className="flex-1 flex items-center gap-2 rounded bg-black/40 border border-white/10 px-2 py-1.5 focus-within:border-sky-500/50 min-w-0">
        <span className="text-[10px] font-mono uppercase text-slate-500 shrink-0">{label}</span>
        <input
          type="number"
          inputMode="decimal"
          step={step}
          min="0"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="bg-transparent text-sm font-mono text-white w-full min-w-0 outline-none tabular-nums"
        />
        <span className="text-[11px] font-mono text-slate-400 shrink-0">{unit}</span>
      </label>
      <button
        type="submit"
        disabled={busy || value === ""}
        className="px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-[11px] font-bold shrink-0"
      >
        {button}
      </button>
    </form>
  );
}

export default function MeterCheck() {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.validation().then(setState).catch(() => {});
  }, []);

  const run = useCallback(async (call) => {
    setBusy(true);
    setError(null);
    try {
      setState(await call());
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const summary = state?.summary;
  const running = state?.running;
  const checks = (state?.checks || []).filter((c) => !c.open);

  return (
    <section className="dash-card p-4 sm:p-5 min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-white/5">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <Plug className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-mono font-bold text-slate-100 uppercase tracking-wider">Wall-Meter Check</h2>
            <div className="text-[10px] text-slate-400">
              Compare our whole-machine reading with a plug-in power meter or smart plug
            </div>
          </div>
        </div>
        <div className="px-2.5 py-1 rounded bg-sky-500/10 border border-sky-500/25 text-[11px] font-mono shrink-0">
          {summary?.checks ? (
            <>
              <span className="text-slate-300">AVG DIFFERENCE: </span>
              <span className={`font-bold tabular-nums ${diffColor(summary.mean_abs_difference_pct)}`}>
                ±{summary.mean_abs_difference_pct.toFixed(1)}%
              </span>
              <span className="text-slate-400"> · {summary.checks} check{summary.checks === 1 ? "" : "s"}</span>
            </>
          ) : (
            <span className="text-slate-400">NO CHECKS YET</span>
          )}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-lg bg-black/30 border border-white/5 p-3 space-y-2 min-w-0">
          <div className="flex items-center gap-1.5">
            <Gauge className="w-3.5 h-3.5 text-sky-400" />
            <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-300">Spot check · watts</h3>
          </div>
          <p className="text-[11px] text-slate-400">
            Hold the load steady for {state?.spot_window_s ?? 30} s, then type what the meter shows. It's compared
            with our average over those seconds.
          </p>
          <NumberForm label="Meter" unit="W" button="Compare" busy={busy} onSubmit={(v) => run(() => api.meterWatts(v))} />
        </div>

        <div className="rounded-lg bg-black/30 border border-white/5 p-3 space-y-2 min-w-0">
          <div className="flex items-center gap-1.5">
            <Timer className="w-3.5 h-3.5 text-sky-400" />
            <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-300">Energy check · kWh</h3>
          </div>
          {running ? (
            <>
              <p className="text-[11px] text-slate-400">
                Started {timeOf(running.started_at)} at{" "}
                <span className="font-mono text-slate-200">{running.meter_start ?? ""}</span> on the meter. Keep the
                device reader running, then type the meter's counter again.
              </p>
              <NumberForm label="End" unit="kWh" button="Finish" busy={busy} onSubmit={(v) => run(() => api.meterFinish(v))} />
            </>
          ) : (
            <>
              <p className="text-[11px] text-slate-400">
                Type the meter's kWh counter, run any workload, then finish. Meters count in 0.01 kWh, so give a laptop
                an hour or more.
              </p>
              <NumberForm label="Start" unit="kWh" button="Start" busy={busy} onSubmit={(v) => run(() => api.meterStart(v))} />
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-3 p-2.5 rounded bg-rose-500/10 border border-rose-500/25 text-rose-300 text-[11px]">{error}</div>
      )}

      {checks.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-[11px] font-mono">
            <thead>
              <tr className="text-[10px] uppercase text-slate-500 border-b border-white/5">
                <th className="text-left py-1.5 pr-2 font-semibold">When</th>
                <th className="text-right py-1.5 px-2 font-semibold">Meter</th>
                <th className="text-right py-1.5 px-2 font-semibold">This app</th>
                <th className="text-right py-1.5 px-2 font-semibold">Difference</th>
                <th className="py-1.5 pl-2" />
              </tr>
            </thead>
            <tbody>
              {checks.map((c) => {
                const fmt = c.unit === "W" ? formatWatts : (v) => formatKwh(v, 3);
                return (
                  <tr key={c.id} className="border-b border-white/[0.04] last:border-0">
                    <td className="py-1.5 pr-2 text-slate-300 whitespace-nowrap">
                      {timeOf(c.started_at)}
                      <span className="text-slate-500"> · {c.unit === "W" ? "spot" : `${c.minutes} min`}</span>
                    </td>
                    <td className="py-1.5 px-2 text-right tabular-nums text-slate-200">{fmt(c.meter)}</td>
                    <td className="py-1.5 px-2 text-right tabular-nums text-slate-200">{fmt(c.app)}</td>
                    <td className={`py-1.5 px-2 text-right tabular-nums font-bold ${diffColor(c.difference_pct ?? 0)}`}>
                      {c.difference_pct != null ? signed(c.difference_pct) : "—"}
                    </td>
                    <td className="py-1.5 pl-2 text-right">
                      <button
                        onClick={() => run(() => api.deleteMeterCheck(c.id))}
                        className="text-slate-500 hover:text-rose-300"
                        title="Remove this check"
                        aria-label="Remove this check"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-3 text-[10px] text-slate-500">
        The meter reads at the wall, so it also counts charger losses (often 5–15%) and battery charging: keep a laptop
        at 100% while checking. Differences are shown as measured, not corrected.
        {busy && <Loader2 className="inline w-3 h-3 ml-1.5 animate-spin" />}
      </p>
    </section>
  );
}
