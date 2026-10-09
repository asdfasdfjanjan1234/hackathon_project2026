import { useState, useMemo } from "react";
import {
  Cpu,
  ArrowUpDown,
  HardDrive,
  Cloud,
} from "lucide-react";
import { peso, formatKwh, formatWatts, shortDate } from "../format";
import { PARTS } from "./AppPowerParts";

// Power class from the average watts while the model was doing work (measured, not a rating).
const POWER_CLASSES = [
  { max: 30, grade: "CLASS A", color: "text-sky-400 border-sky-500/25 bg-sky-500/10" },
  { max: 100, grade: "CLASS B", color: "text-slate-200 border-white/15 bg-white/5" },
  { max: 250, grade: "CLASS C", color: "text-amber-400 border-amber-500/25 bg-amber-500/10" },
  { max: Infinity, grade: "CLASS D", color: "text-rose-400 border-rose-500/25 bg-rose-500/10" },
];

function powerClass(watts) {
  if (watts == null) return { grade: "—", label: "No active time yet", color: "text-slate-400 border-white/10 bg-white/5" };
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
    <section className="dash-card p-4 sm:p-5 flex flex-col justify-between select-none font-mono min-w-0">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-white/5 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wider truncate">
              Runtime Inventory & Power Profiles
            </h2>
            <div className="text-[10px] text-slate-400 font-sans truncate">
              Model execution benchmarks & cost attribution
              {usage?.window && ` · ${shortDate(usage.window.start)} – ${shortDate(usage.window.end)}`}
            </div>
          </div>
        </div>

        {/* Sort Controls */}
        <div className="flex items-center gap-1 text-[11px] shrink-0">
          <span className="text-slate-400 mr-1 text-[10px]">SORT:</span>
          {[
            { id: "kwh", label: "ENERGY" },
            { id: "cost", label: "TARIFF" },
            { id: "name", label: "ID" },
          ].map((s) => (
            <button
              key={s.id}
              onClick={() => toggleSort(s.id)}
              className={`px-2 py-0.5 rounded border text-[10px] transition-colors ${
                sortBy === s.id
                  ? "bg-slate-700 text-sky-300 border-slate-600 font-bold"
                  : "bg-white/[0.02] text-slate-400 border-white/5 hover:text-white"
              }`}
            >
              {s.label} {sortBy === s.id && (sortOrder === "desc" ? "↓" : "↑")}
            </button>
          ))}
        </div>
      </div>

      {/* Model Table List - Smooth Horizontal Scroll on Mobile */}
      <div className="overflow-x-auto my-2 -mx-4 sm:mx-0 px-4 sm:px-0">
        <table className="w-full text-left text-xs border-collapse min-w-[500px]">
          <thead>
            <tr className="border-b border-white/5 text-slate-400 uppercase tracking-wider text-[10px]">
              <th className="py-2.5 px-2 font-bold">MODEL RUNTIME</th>
              <th className="py-2.5 px-2 font-bold">HOST BUS</th>
              <th className="py-2.5 px-2 font-bold">{usage?.window?.short || `${usage?.window_days || 30}D`} ENERGY</th>
              <th className="py-2.5 px-2 font-bold">ATTRIBUTED TARIFF</th>
              <th className="py-2.5 px-2 font-bold text-center">POWER CLASS</th>
              <th className="py-2.5 px-2 font-bold text-right">TELEMETRY</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {models.map((m) => (
              <tr
                key={m.model}
                className="hover:bg-white/[0.02] transition-colors"
              >
                {/* Model ID */}
                <td className="py-2.5 px-2">
                  <div className="flex items-center gap-2">
                    {m.kind === "local" ? (
                      <HardDrive className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    ) : (
                      <Cloud className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    )}
                    <div>
                      <span className="font-bold text-slate-100 block text-xs">
                        {m.model}
                      </span>
                      <span className="text-[9px] text-slate-400 uppercase">
                        {m.kind === "local" ? "LOCAL MODEL" : m.kind === "client" ? "AI APP · THIS DEVICE" : "CLOUD API"}
                      </span>
                    </div>
                  </div>
                </td>

                {/* Host Bus */}
                <td className="py-2.5 px-2 text-[11px] text-slate-400">
                  {m.kind === "local" ? "This device (CPU/GPU)" : m.kind === "client" ? "This device" : "Data center"}
                </td>

                {/* Energy with Progress Bar */}
                <td className="py-2.5 px-2 min-w-[120px]">
                  <div className="space-y-1">
                    <div className="font-bold text-slate-200 tabular-nums text-xs">
                      {formatKwh(m.kwh, 2)}
                    </div>
                    {m.partKwh ? (
                      <>
                        <div className="w-full bg-slate-800 rounded-sm h-1 overflow-hidden">
                          <div className="h-full flex" style={{ width: `${m.percentage}%` }}>
                            {PARTS.map((p, i) => (
                              <div key={p.key} className={p.bar} style={{ width: `${(m.partKwh[i] / m.splitKwh) * 100}%` }} />
                            ))}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-x-1.5 text-[9px] font-mono tabular-nums">
                          {PARTS.map((p, i) => (
                            <span key={p.key} className={p.text}>
                              {p.label} {formatKwh(m.partKwh[i], 2)}
                            </span>
                          ))}
                        </div>
                      </>
                    ) : (
                    <div className="w-full bg-slate-800 rounded-sm h-1 overflow-hidden">
                      <div
                        className={`h-full ${
                          m.kind === "cloud"
                            ? "bg-slate-600"
                            : m.percentage > 50
                            ? "bg-rose-500"
                            : "bg-sky-500"
                        }`}
                        style={{ width: `${m.percentage}%` }}
                      />
                    </div>
                    )}
                  </div>
                </td>

                {/* Tariff */}
                <td className="py-2.5 px-2">
                  <div className="font-bold text-slate-100 tabular-nums text-xs">
                    {peso(m.cost)}
                  </div>
                  <div className="text-[9px] text-slate-400">
                    {m.kind === "cloud" ? "ESTIMATED" : "DIRECT BILL"}
                  </div>
                </td>

                {/* Efficiency Grade (Cyan / Amber / Rose - NO GREEN) */}
                <td className="py-2.5 px-2 text-center">
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold border ${m.efficiency.color}`}
                    title={m.efficiency.label}
                  >
                    {m.efficiency.grade}
                  </span>
                  <div className="text-[9px] text-slate-500 mt-0.5 whitespace-nowrap">{m.efficiency.label}</div>
                </td>

                {/* Source Badge (Cyan, NO GREEN) */}
                <td className="py-2.5 px-2 text-right">
                  <span
                    className={`tech-tag ${
                      m.source === "measured" && usage.data_source !== "sample" ? "tech-tag-live" : "tech-tag-sim"
                    }`}
                    title={
                      usage.data_source === "sample"
                        ? "Synthetic data for John's gaming PC"
                        : m.source === "measured"
                        ? "Measured at the device, split per model by CPU and GPU share"
                        : "Estimated from token counts"
                    }
                  >
                    {usage.data_source === "sample" ? "sample" : m.source === "measured" ? "device · per app" : m.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Energy per host app (VS Code, Terminal, ...), from the device reader */}
      {usage?.by_host?.length > 0 && (
        <div className="mt-2 pt-3 border-t border-white/5">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1.5">By host ({(usage.window?.label || "Last 30 days").toLowerCase()})</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {usage.by_host.map((h) => (
              <div
                key={`${h.app}-${h.host}`}
                className="flex items-center justify-between gap-2 p-1.5 rounded bg-white/[0.02] border border-white/5 text-[11px]"
              >
                <span className="text-slate-200 truncate">
                  {h.app} <span className="text-slate-500">in {h.host}</span>
                </span>
                <span className="text-slate-300 tabular-nums shrink-0">
                  {formatKwh(h.kwh)} · {peso(h.cost)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Industrial Footer */}
      <div className="pt-2 border-t border-white/5 flex flex-wrap items-center justify-between text-[10px] text-slate-400 gap-2">
        <span>
          * Power class: average watts while running (A under 30 W, B under 100 W, C under 250 W, D above). Cloud
          model inference runs in the provider's data center.
        </span>
        <span>INDEX: {models.length} RUNTIMES</span>
      </div>
    </section>
  );
}
