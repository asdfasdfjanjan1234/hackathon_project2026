import { useState, useMemo } from "react";
import {
  Cpu,
  ArrowUpDown,
  HardDrive,
  Cloud,
} from "lucide-react";
import { peso, formatKwh } from "../format";

export default function UsageBreakdown({ usage }) {
  const [sortBy, setSortBy] = useState("kwh");
  const [sortOrder, setSortOrder] = useState("desc");

  const models = useMemo(() => {
    if (!usage?.by_model) return [];

    // All classes styled with precision instrument cyan/amber/rose - NO generic green
    const efficiencyMap = {
      "claude (cloud)": { grade: "CLASS A", label: "Remote DC", color: "text-sky-400 border-sky-500/25 bg-sky-500/10" },
      "llama3:8b": { grade: "CLASS A", label: "75W Nominal", color: "text-sky-400 border-sky-500/25 bg-sky-500/10" },
      "sdxl-turbo": { grade: "CLASS B", label: "220W Batch", color: "text-amber-400 border-amber-500/25 bg-amber-500/10" },
      "llama3:70b": { grade: "CLASS D", label: "280W Peak", color: "text-rose-400 border-rose-500/25 bg-rose-500/10" },
    };

    const maxKwh = Math.max(...usage.by_model.map((m) => m.kwh || 0), 1);

    const list = usage.by_model.map((m) => {
      const eff = efficiencyMap[m.model] || {
        grade: "CLASS B",
        label: "Standard",
        color: "text-slate-300 border-white/10 bg-white/5",
      };
      const percentage = Math.round((m.kwh / maxKwh) * 100);

      return {
        ...m,
        efficiency: eff,
        percentage,
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
              <th className="py-2.5 px-2 font-bold">30D ENERGY</th>
              <th className="py-2.5 px-2 font-bold">ATTRIBUTED TARIFF</th>
              <th className="py-2.5 px-2 font-bold text-center">EFFICIENCY</th>
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
                        {m.kind === "local" ? "LOCAL GPU/NPU" : m.kind === "client" ? "AI APP · THIS DEVICE" : "CLOUD API"}
                      </span>
                    </div>
                  </div>
                </td>

                {/* Host Bus */}
                <td className="py-2.5 px-2 text-[11px] text-slate-400">
                  {m.kind === "local" ? "Metal / MPS" : m.kind === "client" ? "This device" : "Data Center"}
                </td>

                {/* Energy with Progress Bar */}
                <td className="py-2.5 px-2 min-w-[120px]">
                  <div className="space-y-1">
                    <div className="font-bold text-slate-200 tabular-nums text-xs">
                      {formatKwh(m.kwh, 2)}
                    </div>
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
                  >
                    {m.efficiency.grade}
                  </span>
                </td>

                {/* Source Badge (Cyan, NO GREEN) */}
                <td className="py-2.5 px-2 text-right">
                  <span
                    className={`tech-tag ${
                      m.source === "measured" ? "tech-tag-live" : "tech-tag-sim"
                    }`}
                  >
                    {m.source}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Industrial Footer */}
      <div className="pt-2 border-t border-white/5 flex flex-wrap items-center justify-between text-[10px] text-slate-400 gap-2">
        <span>* Provider cloud token inference energy is billed to data center infrastructure.</span>
        <span>INDEX: {models.length} RUNTIMES</span>
      </div>
    </section>
  );
}
