import { useEffect, useState } from "react";
import { api } from "../api/client";
import { CardHeader, MiniTile } from "./Card";
import { ASSETS, DEV_TOOLS, LIMITATIONS, MODELS, PYTHON_LIBRARIES, PYTHON_STDLIB, SERVICES, STACK } from "../disclosure";

const WHERE = {
  device: { label: "This device", className: "tech-tag-pos" },
  team: { label: "Team only", className: "tech-tag-neutral" },
};

// Kilo's model as configured on this computer (ASSISTANT_MODEL), and whether Ollama has it.
const KILO_STATE = {
  ready: { label: "ready", className: "tech-tag-pos" },
  model_missing: { label: "not downloaded", className: "tech-tag-sim" },
  ollama_stopped: { label: "Ollama not running", className: "tech-tag-sim" },
  ollama_missing: { label: "Ollama not installed", className: "tech-tag-sim" },
};

export default function Disclosure() {
  const [kilo, setKilo] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .assistantStatus()
      .then((s) => !cancelled && setKilo(s))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const onDevice = MODELS.filter((m) => m.where === "device").length;
  const parts = ["Backend", "Training", "Promo"].map(
    (part) => `${PYTHON_LIBRARIES.filter((l) => l.part === part).length} ${part.toLowerCase()}`
  );
  const kiloState = kilo && KILO_STATE[kilo.state];

  return (
    <>
      <section className="dash-card p-5 min-w-0">
        <CardHeader title="At a glance" sub="Everything the dashboard shows is computed on this computer" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
          <MiniTile title="Models on this device" value={onDevice} sub={`${MODELS.length - onDevice} more used only by the team`} />
          <MiniTile title="Hosted AI APIs" value="None" sub="Kilo and the forecast run locally" />
          <MiniTile title="Python packages" value={PYTHON_LIBRARIES.length} sub={parts.join(", ")} />
          <MiniTile title="Online services" value={SERVICES.length} sub="Each optional, or for setup or training" />
        </div>
      </section>

      <section className="dash-card p-5 min-w-0">
        <CardHeader title="Models" sub="What each model does and where it runs">
          {kilo?.model && (
            <span className={`tech-tag ${kiloState?.className || "tech-tag-neutral"}`}>
              Kilo here: {kilo.model}
              {kiloState && ` · ${kiloState.label}`}
            </span>
          )}
        </CardHeader>
        <Table head={["Model", "Runs with", "What it does", "Where", "Note"]} minWidth="min-w-[860px]">
          {MODELS.map((m) => (
            <tr key={m.name} className="align-top">
              <td className="py-2.5 px-2 font-semibold text-ink">{m.name}</td>
              <td className="py-2.5 px-2 text-ink-soft whitespace-nowrap">{m.runtime}</td>
              <td className="py-2.5 px-2 text-ink-soft">{m.use}</td>
              <td className="py-2.5 px-2">
                <span className={`tech-tag ${WHERE[m.where].className}`}>{WHERE[m.where].label}</span>
              </td>
              <td className="py-2.5 px-2 text-ink-muted">{m.note}</td>
            </tr>
          ))}
        </Table>
      </section>

      <section className="dash-card p-5 min-w-0">
        <CardHeader title="Python libraries" sub="Pinned in backend/requirements.txt and training/arima_forecast/requirements.txt" />
        <Table head={["Package", "Version", "Part", "What we use it for"]} minWidth="min-w-[640px]">
          {PYTHON_LIBRARIES.map((l) => (
            <tr key={l.name}>
              <td className="py-2 px-2 font-semibold text-ink whitespace-nowrap">{l.name}</td>
              <td className="py-2 px-2 text-ink-soft tabular-nums whitespace-nowrap">{l.version}</td>
              <td className="py-2 px-2">
                <span className="tech-tag tech-tag-neutral">{l.part}</span>
              </td>
              <td className="py-2 px-2 text-ink-soft">{l.use}</td>
            </tr>
          ))}
        </Table>
        <div className="card-foot">
          <span>Also from Python's standard library: {PYTHON_STDLIB}.</span>
        </div>
      </section>

      <section className="dash-card p-5 min-w-0">
        <CardHeader title="Tech stack" sub="Frontend versions as installed from package-lock.json" />
        <Table head={["Layer", "Technologies"]} minWidth="min-w-[560px]">
          {STACK.map((s) => (
            <tr key={s.layer} className="align-top">
              <td className="py-2 px-2 font-semibold text-ink whitespace-nowrap">{s.layer}</td>
              <td className="py-2 px-2 text-ink-soft tabular-nums">{s.items}</td>
            </tr>
          ))}
        </Table>
      </section>

      <section className="dash-card p-5 min-w-0">
        <CardHeader title="APIs and online services" sub="What reaches the internet, and what leaves this computer when it does" />
        <Table head={["Service", "Used for", "Needed", "What leaves this computer", "Without it"]} minWidth="min-w-[860px]">
          {SERVICES.map((s) => (
            <tr key={s.name} className="align-top">
              <td className="py-2.5 px-2 font-semibold text-ink">{s.name}</td>
              <td className="py-2.5 px-2 text-ink-soft">{s.use}</td>
              <td className="py-2.5 px-2">
                <span className="tech-tag tech-tag-neutral">{s.needed}</span>
              </td>
              <td className="py-2.5 px-2 text-ink-soft">{s.sends}</td>
              <td className="py-2.5 px-2 text-ink-muted">{s.without}</td>
            </tr>
          ))}
        </Table>
        <div className="card-foot">
          <span>
            No hosted LLM API and no paid cloud service. Cloud AI tools you run yourself (Claude Code, Copilot, Codex)
            use the internet on their own; Kilo What? only reads their local logs.
          </span>
        </div>
      </section>

      <section className="dash-card p-5 min-w-0">
        <CardHeader title="Existing assets and data" sub="Made by others and used here" />
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
          {ASSETS.map((a) => (
            <div key={a.name} className="inset-panel p-3 min-w-0">
              <dt className="text-sm font-semibold text-ink">{a.name}</dt>
              <dd className="text-xs text-ink-soft leading-relaxed mt-1">{a.detail}</dd>
            </div>
          ))}
        </dl>
        <div className="card-foot">
          <span>Open-source libraries above are used under their own licenses. All project code was written for this hackathon.</span>
        </div>
      </section>

      <section className="dash-card p-5 min-w-0">
        <CardHeader title="Limitations" sub="What the numbers can't tell you, and what isn't finished. Estimated figures are labeled as estimated" />
        <div className="columns-1 lg:columns-2 gap-3 mt-4">
          {LIMITATIONS.map((g) => (
            <div key={g.area} className="inset-panel p-3 mb-3 min-w-0 break-inside-avoid">
              <h3 className="eyebrow">{g.area}</h3>
              <dl className="mt-2 space-y-2.5">
                {g.items.map((l) => (
                  <div key={l.name}>
                    <dt className="text-sm font-semibold text-ink">{l.name}</dt>
                    <dd className="text-xs text-ink-soft leading-relaxed mt-0.5">{l.detail}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      </section>

      <section className="dash-card p-5 min-w-0">
        <CardHeader title="AI development tools" sub="Used to build Kilo What?, not part of the running app" />
        <ul className="mt-4 space-y-2 text-sm">
          {DEV_TOOLS.map((t) => (
            <li key={t.name} className="text-ink-soft">
              <span className="font-semibold text-ink">{t.name}:</span> {t.use}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function Table({ head, minWidth, children }) {
  return (
    <div className="overflow-x-auto my-2 -mx-5 sm:mx-0 px-5 sm:px-0">
      <table className={`w-full text-left text-sm border-collapse ${minWidth}`}>
        <thead>
          <tr className="border-b border-line">
            {head.map((h) => (
              <th key={h} className="th">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}
