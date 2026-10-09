import { peso } from "../format";

export default function Recommendations({ recs }) {
  return (
    <section className="card">
      <h2>Recommendations</h2>
      <ul className="recs">
        {recs.recommendations.map((r, i) => (
          <li key={i}>
            <span className={`action ${r.action.toLowerCase()}`}>{r.action}</span>
            <span className="msg">{r.message}</span>
            <span className="save">saves {peso(r.monthly_savings)}/mo</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
