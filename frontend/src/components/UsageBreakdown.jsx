import { useState, useMemo } from "react";
import {
  HardDrive,
  Cloud,
} from "lucide-react";
import { peso, formatKwh, formatWatts, shortDate } from "../format";
import { PARTS } from "./AppPowerParts";

// Power class from the average watts while the model was doing work (measured, not a rating).
const POWER_CLASSES = [
  { max: 30, grade: "Class A", tag: "tech-tag-pos" },
  { max: 100, grade: "Class B", tag: "tech-tag-neutral" },
  { max: 250, grade: "Class C", tag: "tech-tag-sim" },
  { max: Infinity, grade: "Class D", tag: "tech-tag-alert" },
];

function powerClass(watts) {
  if (watts == null) return { grade: "—", label: "No active time yet", tag: "tech-tag-neutral" };
  const c = POWER_CLASSES.find((p) => watts < p.max);
  return { ...c, label: `${formatWatts(watts)} while running` };
}

export default function UsageBreakdown({ usage }) {
  const [sortBy, setSortBy] = useState("kwh");
  const [sortOrder, setSortOrder] = useState("desc");

  const models = useMemo(() => {
    if (!usage?.by_model) return [];

    const maxKwh = Math.max(...usage.by_model.map((m) => m.kwh || 0), 1e-9);

    const list = usage.by_model.map((m) => {
      const eff = powerClass(m.active_watts);
      const percentage = Math.round((m.kwh / maxKwh) * 100);

      // CPU / GPU / RAM kWh, for models measured on this device after the split was recorded.
      const split = usage.parts_by_model?.[m.model];
      const partKwh = split ? PARTS.map((p) => split[`${p.key}_kwh`] || 0) : null;
      const splitKwh = partKwh ? partKwh.reduce((a, b) => a + b, 0) : 0;

      return {
        ...m,
        efficiency: eff,
        percentage,
        partKwh: splitKwh > 0 ? partKwh : null,
        splitKwh,
      };
    });

    list.sort((a, b) => {
      let diff = 0;
      if (sortBy === "kwh") diff = a.kwh - b.kwh;
      else if (sortBy === "cost") diff = a.cost - b.cost;
      else if (sortBy === "name") diff = a.model.localeCompare(b.model);
      return sortOrder === "desc" ? -diff : diff;
    });

    return list;
  }, [usage, sortBy, sortOrder]);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  return (
    <section className="dash-card p-5 flex flex-col justify-between min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between pb-4 border-b border-line gap-3">
        <div className="min-w-0">
          <h2 className="card-title">Runtime inventory & power profiles</h2>
          <div className="card-sub mt-0.5">
            Model execution benchmarks & cost attribution
            {usage?.window && ` · ${shortDate(usage.window.start)} – ${shortDate(usage.window.end)}`}
          </div>
        </div>

        {/* Sort Controls */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-ink-muted">Sort:</span>
          <div className="seg" role="group" aria-label="Sort by">
            {[
              { id: "kwh", label: "Energy" },
              { id: "cost", label: "Tariff" },
              { id: "name", label: "ID" },
            ].map((s) => (
              <button
                key={s.id}
                onClick={() => toggleSort(s.id)}
                aria-pressed={sortBy === s.id}
                className={`seg-item ${sortBy === s.id ? "seg-item-active" : ""}`}
              >
                {s.label} {sortBy === s.id && (sortOrder === "desc" ? "↓" : "↑")}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Model table: scrolls sideways on small screens */}
      <div className="overflow-x-auto my-2 -mx-5 sm:mx-0 px-5 sm:px-0">
        <table className="w-full text-left text-sm border-collapse min-w-[640px]">
          <thead>
            <tr className="border-b border-line">
              <th className="th">Model runtime</th>
              <th className="th">Host bus</th>
              <th className="th">{usage?.window?.short || `${usage?.window_days || 30}D`} energy</th>
              <th className="th">Attributed tariff</th>
              <th className="th text-center">Power class</th>
              <th className="th text-right">Telemetry</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {models.map((m) => (
              <tr key={m.model} className="hover:bg-sunken transition-colors">
                {/* Model ID */}
                <td className="py-3 px-2">
                  <div className="flex items-center gap-2.5">
                    {m.kind === "local" ? (
                      <HardDrive className="w-4 h-4 text-ink-muted shrink-0" />
                    ) : (
                      <Cloud className="w-4 h-4 text-ink-muted shrink-0" />
                    )}
                    <div>
                      <span className="font-semibold text-ink block">{m.model}</span>
                      <span className="text-xs text-ink-muted">
                        {m.kind === "local" ? "Local model" : m.kind === "client" ? "AI app · this device" : "Cloud API"}
                      </span>
                    </div>
                  </div>
                </td>

                {/* Host Bus */}
                <td className="py-3 px-2 text-xs text-ink-soft">
                  {m.kind === "local" ? "This device (CPU/GPU)" : m.kind === "client" ? "This device" : "Data center"}
                </td>

                {/* Energy with Progress Bar */}
                <td className="py-3 px-2 min-w-[140px]">
                  <div className="space-y-1.5">
                    <div className="font-semibold text-ink tabular-nums">{formatKwh(m.kwh, 2)}</div>
                    {m.partKwh ? (
                      <>
                        <div className="w-full bg-line rounded-full h-1.5 overflow-hidden">
                          <div className="h-full flex" style={{ width: `${m.percentage}%` }}>
                            {PARTS.map((p, i) => (
                              <div key={p.key} className={p.bar} style={{ width: `${(m.partKwh[i] / m.splitKwh) * 100}%` }} />
                            ))}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-x-2 text-[11px] tabular-nums text-ink-muted">
                          {PARTS.map((p, i) => (
                            <span key={p.key} className="inline-flex items-center gap-1">
                              <span className={`w-1.5 h-1.5 rounded-full ${p.bar}`} />
                              {p.label} {formatKwh(m.partKwh[i], 2)}
                            </span>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="w-full bg-line rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${m.kind === "cloud" ? "bg-viz-grey" : "bg-accent"}`}
                          style={{ width: `${m.percentage}%` }}
                        />
                      </div>
                    )}
                  </div>
                </td>

                {/* Tariff */}
                <td className="py-3 px-2">
                  <div className="font-bold text-ink tabular-nums">{peso(m.cost)}</div>
                  <div className="text-xs text-ink-muted">{m.kind === "cloud" ? "Estimated" : "Direct bill"}</div>
                </td>

                {/* Power class */}
                <td className="py-3 px-2 text-center">
                  <span className={`tech-tag ${m.efficiency.tag}`} title={m.efficiency.label}>
                    {m.efficiency.grade}
                  </span>
                  <div className="text-[11px] text-ink-muted mt-1 whitespace-nowrap tabular-nums">{m.efficiency.label}</div>
                </td>

                {/* Source badge */}
                <td className="py-3 px-2 text-right">
                  <span
                    className={`tech-tag ${m.source === "measured" ? "tech-tag-live" : "tech-tag-sim"}`}
                    title={
                      m.source === "measured"
                        ? "Measured at the device, split per model by CPU and GPU share"
                        : "Estimated from token counts"
                    }
                  >
                    {m.source === "measured" ? "device · per app" : m.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Energy per host app (VS Code, Terminal, ...), from the device reader */}
      {usage?.by_host?.length > 0 && (
        <div className="mt-2 pt-4 border-t border-line">
          <div className="text-xs font-medium text-ink-muted mb-2">By host ({(usage.window?.label || "Last 30 days").toLowerCase()})</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {usage.by_host.map((h) => (
              <div
                key={`${h.app}-${h.host}`}
                className="flex items-center justify-between gap-2 px-3 py-2 inset-panel text-sm"
              >
                <span className="font-medium text-ink truncate">
                  {h.app} <span className="font-normal text-ink-muted">in {h.host}</span>
                </span>
                <span className="text-ink-soft tabular-nums shrink-0 text-xs">
                  {formatKwh(h.kwh)} · <span className="font-semibold text-ink">{peso(h.cost)}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-line flex flex-wrap items-center justify-between text-xs text-ink-muted gap-2">
        <span>
          * Power class: average watts while running (A under 30 W, B under 100 W, C under 250 W, D above). Cloud
          model inference runs in the provider's data center.
        </span>
        <span className="tabular-nums">Index: {models.length} runtimes</span>
      </div>
    </section>
  );
}
