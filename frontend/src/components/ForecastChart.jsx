import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { peso } from "../format";

export default function ForecastChart({ forecast, recs }) {
  const rows = [
    { name: "Without AI", bill: forecast.baseline_bill },
    { name: "Keep using as is", bill: forecast.forecast_bill },
    { name: "Follow recommendations", bill: recs.bill_with_recommendations },
  ];

  return (
    <section className="card">
      <h2>Bill forecast for {forecast.month}</h2>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" />
          <YAxis tickFormatter={peso} width={70} />
          <Tooltip formatter={(v) => peso(v)} />
          <Bar dataKey="bill" fill="#4f7cff" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
