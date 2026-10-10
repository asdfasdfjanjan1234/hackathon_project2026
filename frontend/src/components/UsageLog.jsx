import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api } from "../api/client";
import { peso, formatAppWatts, formatDuration, formatTimestamp, shortDate } from "../format";
import BrandIcon from "./BrandIcon";
import { CardHeader } from "./Card";

const REFRESH_MS = 30000;

// The breakdowns the backend returns (usage_log.DIMENSIONS), and what a group with no value is called.
const DIMENSIONS = [
  { id: "date", label: "Date", title: "date", column: "Date" },
  { id: "ide", label: "IDE", title: "IDE", column: "IDE or host app" },
  { id: "app", label: "AI app", title: "AI app", column: "AI app" },
  { id: "model", label: "Model", title: "model", column: "Model" },
  { id: "effort", label: "Effort", title: "effort", column: "Effort", none: "Not logged by the app" },
];

const SLOTS = [
  { s: 60, label: "1 min" },
  { s: 900, label: "15 min" },
  { s: 3600, label: "1 hour" },
];

const NOT_LOGGED = "Not logged";
const hours = (seconds) => seconds / 3600;
// Watt-hours with the decimals a single record needs: one app over a few minutes is a fraction of a Wh.
const energy = (wh) => {
  if (wh >= 1000) return `${(wh / 1000).toFixed(2)} kWh`;
  return `${wh.toFixed(wh >= 10 ? 1 : wh >= 0.1 ? 2 : 4)} Wh`;
};

export default function UsageLog({ params, range }) {
  const [log, setLog] = useState(null);
  const [error, setError] = useState(null);
  const [dimension, setDimension] = useState("date");
  const [slot, setSlot] = useState(900);

  useEffect(() => {
    let current = true;
    const load = () =>
      api
        .usageLog(params, range, slot)
        .then((d) => {
          if (!current) return;
          setLog(d);
          setError(null);
        })
        .catch((e) => current && setError(e.message));
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [params, range, slot]);

  if (!log) {
    return error ? (
      <div role="alert" className="empty-state">Couldn't load the usage log: {error}</div>
    ) : (
      <div className="dash-card h-64 animate-pulse" aria-busy="true" aria-label="Loading" />
    );
  }

  const dim = DIMENSIONS.find((d) => d.id === dimension);
  const rows = log.totals[dimension] || [];
  const windowLabel = `${shortDate(log.window.start)} – ${shortDate(log.window.end)}`;

  return (
    <>
      <section className="dash-card p-5 min-w-0">
        <CardHeader
          title={`Total energy by ${dim.title}`}
          sub={`Watts of every reading added up over time · ${windowLabel}`}
        >
          <div className="seg" role="group" aria-label="Group by">
            {DIMENSIONS.map((d) => (
              <button
                key={d.id}
                onClick={() => setDimension(d.id)}
                aria-pressed={dimension === d.id}
                className={`seg-item ${dimension === d.id ? "seg-item-active" : ""}`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </CardHeader>

        <div className="overflow-x-auto my-2 -mx-5 sm:mx-0 px-5 sm:px-0">
          <table className="w-full text-left text-sm border-collapse min-w-[42.5rem]">
            <thead>
              <tr className="border-b border-line">
                <th className="th">{dim.column}</th>
                <th className="th">Energy</th>
                <th className="th text-right">Share</th>
                <th className="th text-right">Average watts</th>
                <th className="th text-right">Peak watts</th>
                <th className="th text-right">Time recorded</th>
                <th className="th text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-ink-muted">
                    No AI readings recorded in this window.
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.key ?? ""} className="hover:bg-sunken transition-colors tabular-nums">
                  <td className="py-2.5 px-2 font-semibold text-ink">
                    <GroupName dimension={dimension} value={r.key} none={dim.none} />
                  </td>
                  <td className="py-2.5 px-2 min-w-[9.375rem]">
                    <div className="font-semibold text-ink">{energy(r.wh)}</div>
                    <div className="meter w-full bg-line rounded-full h-1.5 overflow-hidden mt-1.5">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${r.share * 100}%` }} />
                    </div>
                  </td>
                  <td className="py-2.5 px-2 text-right text-ink-soft">{(r.share * 100).toFixed(1)}%</td>
                  <td className="py-2.5 px-2 text-right text-ink-soft">{formatAppWatts(r.avg_watts)}</td>
                  <td className="py-2.5 px-2 text-right text-ink-soft">{formatAppWatts(r.peak_watts)}</td>
                  <td className="py-2.5 px-2 text-right text-ink-soft">{formatDuration(hours(r.seconds))}</td>
                  <td className="py-2.5 px-2 text-right font-semibold text-ink">{peso(r.cost)}</td>
                </tr>
              ))}
            </tbody>
            {rows.length > 0 && (
              <tfoot>
                <tr className="border-t border-line-strong tabular-nums font-semibold text-ink">
                  <td className="py-2.5 px-2">Total</td>
                  <td className="py-2.5 px-2">{energy(log.total.wh)}</td>
                  <td className="py-2.5 px-2 text-right">100%</td>
                  <td className="py-2.5 px-2 text-right">{formatAppWatts(log.total.avg_watts)}</td>
                  <td className="py-2.5 px-2 text-right">{formatAppWatts(log.total.peak_watts)}</td>
                  <td className="py-2.5 px-2 text-right">{formatDuration(hours(log.total.seconds))}</td>
                  <td className="py-2.5 px-2 text-right">{peso(log.total.cost)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>

        <div className="card-foot">
          <span>
            Every breakdown adds up to the same total, because each reading belongs to exactly one group. Time and
            average watts are per app, so apps running at once each count their own seconds. Watts are what the app
            drew on this device; a cloud model's own inference runs in the provider's data center.
          </span>
          <span className="tabular-nums">{log.total.readings.toLocaleString("en-PH")} readings</span>
        </div>
      </section>

      <Formula log={log} />

      <section className="dash-card p-5 min-w-0">
        <CardHeader
          title="Records"
          sub={`One row per time slot, IDE, model and effort, newest first · ${windowLabel}`}
        >
          <span className="text-xs text-ink-muted">Slot</span>
          <div className="seg" role="group" aria-label="Time slot per record">
            {SLOTS.map((o) => (
              <button
                key={o.s}
                onClick={() => setSlot(o.s)}
                aria-pressed={slot === o.s}
                className={`seg-item ${slot === o.s ? "seg-item-active" : ""}`}
              >
                {o.label}
              </button>
            ))}
          </div>
          <a href={api.usageLogCsvUrl(range, slot)} download className="btn">
            <Download className="w-3.5 h-3.5" /> CSV
          </a>
        </CardHeader>

        <div className="overflow-x-auto my-2 -mx-5 sm:mx-0 px-5 sm:px-0">
          <table className="w-full text-left text-sm border-collapse min-w-[53.75rem]">
            <thead>
              <tr className="border-b border-line">
                <th className="th">First reading</th>
                <th className="th">Last reading</th>
                <th className="th">IDE</th>
                <th className="th">AI app</th>
                <th className="th">Model</th>
                <th className="th">Effort</th>
                <th className="th text-right">Average watts</th>
                <th className="th text-right">Peak watts</th>
                <th className="th text-right">Time</th>
                <th className="th text-right">Energy</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {log.records.length === 0 && (
                <tr>
                  <td colSpan={10} className="py-6 text-center text-ink-muted">
                    No records yet. Start the device reader in This device.
                  </td>
                </tr>
              )}
              {log.records.map((r) => (
                <tr
                  key={`${r.start_ts}-${r.ide}-${r.app}-${r.model_name}-${r.effort}`}
                  className="hover:bg-sunken transition-colors tabular-nums"
                >
                  <td className="py-2 px-2 text-ink whitespace-nowrap">{formatTimestamp(r.start_ts)}</td>
                  <td className="py-2 px-2 text-ink-soft whitespace-nowrap">{formatTimestamp(r.end_ts)}</td>
                  <td className="py-2 px-2 text-ink whitespace-nowrap">
                    <BrandIcon name={r.ide} className="w-3.5 h-3.5" /> {r.ide}
                  </td>
                  <td className="py-2 px-2 text-ink-soft whitespace-nowrap">{r.app}</td>
                  <td className="py-2 px-2 text-ink">{r.model_name || <span className="text-ink-muted">{NOT_LOGGED}</span>}</td>
                  <td className="py-2 px-2">
                    {r.effort ? (
                      <span className="tech-tag tech-tag-neutral">{r.effort}</span>
                    ) : (
                      <span className="text-ink-muted">—</span>
                    )}
                  </td>
                  <td className="py-2 px-2 text-right text-ink-soft">{formatAppWatts(r.avg_watts)}</td>
                  <td className="py-2 px-2 text-right text-ink-soft">{formatAppWatts(r.peak_watts)}</td>
                  <td className="py-2 px-2 text-right text-ink-soft">{formatDuration(hours(r.seconds))}</td>
                  <td className="py-2 px-2 text-right font-semibold text-ink">{energy(r.wh)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card-foot">
          <span>
            Each record adds up the readings (one about every 2 seconds) that share a slot, IDE, model and effort.
            Effort is the reasoning effort the app asked its model for, where the app logs it.
          </span>
          <span className="tabular-nums">
            {log.records_truncated
              ? `Newest ${log.records.length} records · the CSV has all of them`
              : `${log.records.length} ${log.records.length === 1 ? "record" : "records"}`}
          </span>
        </div>
      </section>
    </>
  );
}

function GroupName({ dimension, value, none }) {
  if (value == null) return <span className="font-normal text-ink-muted">{none || NOT_LOGGED}</span>;
  if (dimension === "date") {
    return new Date(`${value}T00:00:00`).toLocaleDateString("en-PH", {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }
  if (dimension === "effort") return <span className="tech-tag tech-tag-neutral">{value}</span>;
  return (
    <>
      <BrandIcon name={value} className="w-3.5 h-3.5" /> {value}
    </>
  );
}

// The formula behind every figure in the log, with the window's own numbers put into it.
function Formula({ log }) {
  const { total } = log;
  const sample = log.records.find((r) => r.wh > 0);
  return (
    <section className="dash-card p-5 min-w-0">
      <CardHeader title="How the totals are computed" sub="The same sum for a date, an IDE, a model or an effort level" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <div className="inset-panel p-4 space-y-3 text-ink tabular-nums">
          <Equation name="Energy of a group">
            E<sub>G</sub> = Σ<sub>i ∈ G</sub> P<sub>i</sub> × Δt<sub>i</sub> ÷ 3600
          </Equation>
          <Equation name="Average watts of a group">
            P̄<sub>G</sub> = Σ P<sub>i</sub> × Δt<sub>i</sub> ÷ Σ Δt<sub>i</sub>
          </Equation>
          <Equation name="Cost of a group">
            C<sub>G</sub> = E<sub>G</sub> ÷ 1000 × rate
          </Equation>
          <Equation name="Watts of one reading">
            P<sub>i</sub> = P<sub>CPU</sub> + P<sub>GPU</sub> + P<sub>memory</sub>
          </Equation>
        </div>

        <dl className="text-sm text-ink-soft space-y-2 leading-relaxed">
          <Term symbol={<>P<sub>i</sub></>}>
            watts attributed to one AI app in reading i: its share of this machine's CPU, GPU and memory power
            above idle.
          </Term>
          <Term symbol={<>Δt<sub>i</sub></>}>seconds since the previous reading (about 2).</Term>
          <Term symbol="G">
            the readings in a group: one date, one IDE, one model, one effort level, or any combination of them.
          </Term>
          <Term symbol={<>E<sub>G</sub></>}>
            energy in watt-hours. Watts × seconds is joules, and 3600 joules is 1 Wh. 1000 Wh is 1 kWh.
          </Term>
          <Term symbol="rate">your electricity rate, {peso(log.rate_per_kwh)} per kWh.</Term>
        </dl>
      </div>

      {total.avg_watts != null && (
        <div className="mt-4 pt-4 border-t border-line text-sm text-ink-soft space-y-1.5 tabular-nums">
          <div className="text-xs font-medium text-ink-muted">With this window's numbers</div>
          <div>
            All groups: {(total.wh / hours(total.seconds)).toPrecision(5)} W average × {hours(total.seconds).toFixed(2)} h
            recorded = <span className="font-semibold text-ink">{energy(total.wh)}</span>, and{" "}
            {(total.wh / 1000).toFixed(4)} kWh × {peso(log.rate_per_kwh)} ={" "}
            <span className="font-semibold text-ink">{peso(total.cost)}</span>
          </div>
          {sample && (
            <div>
              One record ({sample.app} in {sample.ide}, {formatTimestamp(sample.start_ts)}): {sample.avg_watts.toFixed(4)} W
              × {sample.seconds.toFixed(2)} s ÷ 3600 ={" "}
              <span className="font-semibold text-ink">{sample.wh.toFixed(4)} Wh</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Equation({ name, children }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{name}</div>
      <div className="text-base font-semibold [&_sub]:text-2xs [&_sub]:font-medium">{children}</div>
    </div>
  );
}

function Term({ symbol, children }) {
  return (
    <div className="flex gap-3">
      <dt className="w-10 shrink-0 font-semibold text-ink [&_sub]:text-2xs">{symbol}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}
