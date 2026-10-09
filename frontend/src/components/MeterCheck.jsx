import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Trash2, Timer, Gauge, Loader2, AlertTriangle } from "lucide-react";
import { CardHeader } from "./Card";
import { formatWatts, formatKwh } from "../format";

// How close our whole-machine reading is to a plug-in power meter at the wall.
const diffColor = (pct) => {
  const a = Math.abs(pct);
  if (a <= 10) return "text-pos";
  if (a <= 20) return "text-warn";
  return "text-neg";
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
      <label className="field-box flex-1">
        <span className="text-xs font-medium text-ink-muted shrink-0">{label}</span>
        <input
          type="number"
          inputMode="decimal"
          step={step}
          min="0"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="bg-transparent text-sm text-ink w-full min-w-0 focus:outline-none tabular-nums"
        />
        <span className="text-xs text-ink-muted shrink-0">{unit}</span>
      </label>
      <button type="submit" disabled={busy || value === ""} className="btn-primary shrink-0">
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
    <section className="dash-card p-5 min-w-0">
      <CardHeader title="Wall-meter check" sub="Compare our whole-machine reading with a plug-in power meter or smart plug">
        <span className="tech-tag tech-tag-neutral tabular-nums">
          {summary?.checks ? (
            <>
              <span>Avg difference:</span>
              <span className={`font-semibold ${diffColor(summary.mean_abs_difference_pct)}`}>
                ±{summary.mean_abs_difference_pct.toFixed(1)}%
              </span>
              <span>· {summary.checks} check{summary.checks === 1 ? "" : "s"}</span>
            </>
          ) : (
            "No checks yet"
          )}
        </span>
      </CardHeader>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="inset-panel p-4 space-y-2.5 min-w-0">
          <h3 className="text-sm font-semibold text-ink flex items-center gap-1.5">
            <Gauge className="w-4 h-4 text-ink-muted" /> Spot check · watts
          </h3>
          <p className="text-xs text-ink-soft leading-relaxed">
            Hold the load steady for {state?.spot_window_s ?? 30} s, then type what the meter shows. It's compared
            with our average over those seconds.
          </p>
          <NumberForm label="Meter" unit="W" button="Compare" busy={busy} onSubmit={(v) => run(() => api.meterWatts(v))} />
        </div>

        <div className="inset-panel p-4 space-y-2.5 min-w-0">
          <h3 className="text-sm font-semibold text-ink flex items-center gap-1.5">
            <Timer className="w-4 h-4 text-ink-muted" /> Energy check · kWh
          </h3>
          {running ? (
            <>
              <p className="text-xs text-ink-soft leading-relaxed">
                Started {timeOf(running.started_at)} at{" "}
                <span className="font-medium text-ink tabular-nums">{running.meter_start ?? ""}</span> on the meter. Keep the
                device reader running, then type the meter's counter again.
              </p>
              <NumberForm label="End" unit="kWh" button="Finish" busy={busy} onSubmit={(v) => run(() => api.meterFinish(v))} />
            </>
          ) : (
            <>
              <p className="text-xs text-ink-soft leading-relaxed">
                Type the meter's kWh counter, run any workload, then finish. Meters count in 0.01 kWh, so give a laptop
                an hour or more.
              </p>
              <NumberForm label="Start" unit="kWh" button="Start" busy={busy} onSubmit={(v) => run(() => api.meterStart(v))} />
            </>
          )}
        </div>
      </div>

      {error && (
        <div role="alert" className="notice notice-neg mt-3">
          <AlertTriangle />
          <span>{error}</span>
        </div>
      )}

      {checks.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className="th text-left pl-0">When</th>
                <th className="th text-right">Meter</th>
                <th className="th text-right">This app</th>
                <th className="th text-right">Difference</th>
                <th className="th" />
              </tr>
            </thead>
            <tbody>
              {checks.map((c) => {
                const fmt = c.unit === "W" ? formatWatts : (v) => formatKwh(v, 3);
                return (
                  <tr key={c.id} className="border-b border-line last:border-0">
                    <td className="py-2 pr-2 text-ink-soft whitespace-nowrap">
                      {timeOf(c.started_at)}
                      <span className="text-ink-muted"> · {c.unit === "W" ? "spot" : `${c.minutes} min`}</span>
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-ink">{fmt(c.meter)}</td>
                    <td className="py-2 px-2 text-right tabular-nums text-ink">{fmt(c.app)}</td>
                    <td className={`py-2 px-2 text-right tabular-nums font-semibold ${diffColor(c.difference_pct ?? 0)}`}>
                      {c.difference_pct != null ? signed(c.difference_pct) : "—"}
                    </td>
                    <td className="py-2 pl-2 text-right">
                      <button
                        onClick={() => run(() => api.deleteMeterCheck(c.id))}
                        className="btn-icon h-7 w-7 hover:text-neg"
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

      <p className="card-foot block leading-relaxed">
        The meter reads at the wall, so it also counts charger losses (often 5–15%) and battery charging: keep a laptop
        at 100% while checking. Differences are shown as measured, not corrected.
        {busy && <Loader2 className="inline w-3 h-3 ml-1.5 animate-spin" />}
      </p>
    </section>
  );
}
