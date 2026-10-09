import { peso } from "../format";

export default function BillSummary({ forecast, recs }) {
  return (
    <section className="card">
      <h2>This month's bill</h2>
      <dl className="bill">
        <dt>Without AI</dt><dd>{peso(forecast.baseline_bill)}</dd>
        <dt>Forecast with AI</dt><dd className="bad">{peso(forecast.forecast_bill)}</dd>
        <dt>With recommendations</dt><dd className="good">{peso(recs.bill_with_recommendations)}</dd>
      </dl>
    </section>
  );
}
