import { peso } from "../format";

const HEADLINES = {
  major: "Yes — AI is the main reason your bill went up",
  contributing: "Partly — AI is one of the reasons your bill went up",
  minor: "Barely — AI added only a little to your bill",
  none: "No — AI did not raise your bill",
  no_increase: "Your bill did not go up",
};

export default function BillImpact({ impact }) {
  const parts = [
    { key: "ai", label: "AI (measured)", value: impact.ai_effect },
    { key: "rate", label: "Rate change", value: impact.rate_effect },
    { key: "other", label: "Other usage", value: impact.other_effect },
  ].filter((p) => p.value > 0);
  const total = parts.reduce((s, p) => s + p.value, 0);

  return (
    <section className="card">
      <h2>Did AI increase your bill?</h2>
      <p className={`verdict ${impact.verdict}`}>{HEADLINES[impact.verdict]}</p>
      <p>
        Bill went from {peso(impact.baseline_bill)} to {peso(impact.current_bill)} (+{peso(impact.increase)}).
        {impact.ai_share !== null && <> AI explains <strong>{peso(impact.ai_effect)}</strong> ({Math.round(impact.ai_share * 100)}%) of the increase.</>}
      </p>
      {total > 0 && (
        <>
          <div className="stack">
            {parts.map((p) => (
              <div key={p.key} className={`seg ${p.key}`} style={{ flexGrow: p.value }} title={`${p.label}: ${peso(p.value)}`} />
            ))}
          </div>
          <ul className="legend">
            {parts.map((p) => (
              <li key={p.key}><span className={`dot ${p.key}`} />{p.label}: {peso(p.value)}</li>
            ))}
          </ul>
        </>
      )}
      <p className="muted">
        Based on {impact.local_ai_kwh} kWh from local models. Cloud AI (~{impact.cloud_ai_kwh_estimated} kWh, estimated) is
        billed to the provider's data center, so it isn't counted.
      </p>
    </section>
  );
}
