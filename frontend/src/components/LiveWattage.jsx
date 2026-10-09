import { useEffect, useState } from "react";
import { api } from "../api/client";

const SOURCE_LABELS = {
  collector: "measured · collector",
  battery: "measured · battery sensor",
  powermetrics: "measured · powermetrics",
  "nvidia-smi": "measured · nvidia-smi",
  simulated: "simulated",
};

export default function LiveWattage() {
  const [reading, setReading] = useState(null);

  useEffect(() => {
    const poll = () => api.live().then(setReading).catch(() => {});
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []);

  if (!reading) return <section className="card"><h2>Live power</h2><p className="big">—</p></section>;

  const model = reading.power_model;
  return (
    <section className="card">
      <h2>Live power</h2>
      <p className="big">{reading.watts} W</p>
      <span className={`tag ${reading.simulated ? "estimated" : "measured"}`}>{SOURCE_LABELS[reading.source] ?? reading.source}</span>
      {reading.source === "collector" ? (
        <>
          <p className="muted">
            CPU {reading.cpu_percent}% · GPU {reading.gpu_percent}%
            {reading.measured_watts != null && <> · battery sensor {reading.measured_watts} W</>}
          </p>
          <p><strong>AI apps: {reading.ai_watts} W</strong></p>
          <ul className="apps">
            {reading.apps.map((a) => (
              <li key={a.name}>
                <span>{a.name} <span className="muted">({a.kind})</span></span>
                <span>{a.watts.toFixed(2)} W</span>
              </li>
            ))}
            {reading.apps.length === 0 && <li className="muted">No AI apps running</li>}
          </ul>
          <p className="muted">
            {model.fitted_on
              ? `Power model fitted on ${model.fitted_on} readings from this device.`
              : "Using default power model until enough readings are collected."}
          </p>
        </>
      ) : (
        <p className="muted">Start <code>python collect.py</code> to see power per AI app.</p>
      )}
    </section>
  );
}
