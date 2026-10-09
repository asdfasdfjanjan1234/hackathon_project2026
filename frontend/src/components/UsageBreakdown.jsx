import { peso } from "../format";

export default function UsageBreakdown({ usage }) {
  return (
    <section className="card">
      <h2>Usage by model (last 30 days)</h2>
      <table>
        <thead>
          <tr><th>Model</th><th>Type</th><th>kWh</th><th>Cost</th><th>Source</th></tr>
        </thead>
        <tbody>
          {usage.by_model.map((m) => (
            <tr key={m.model}>
              <td>{m.model}</td>
              <td>{m.kind}</td>
              <td>{m.kwh}</td>
              <td>{peso(m.cost)}</td>
              <td><span className={`tag ${m.source}`}>{m.source}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
