import { useEffect, useState } from "react";
import { api } from "./api/client";
import LiveWattage from "./components/LiveWattage";
import BillSummary from "./components/BillSummary";
import UsageBreakdown from "./components/UsageBreakdown";
import ForecastChart from "./components/ForecastChart";
import Recommendations from "./components/Recommendations";

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.usage(), api.forecast(), api.recommendations()])
      .then(([usage, forecast, recs]) => setData({ usage, forecast, recs }))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <main className="container"><p className="error">Could not reach the backend: {error}</p></main>;
  if (!data) return <main className="container"><p>Loading…</p></main>;

  return (
    <main className="container">
      <header>
        <h1>AI Wattage Tracker</h1>
        <p className="subtitle">How much electricity your AI models use, and what it does to your bill.</p>
      </header>
      <div className="grid">
        <LiveWattage />
        <BillSummary forecast={data.forecast} recs={data.recs} />
      </div>
      <UsageBreakdown usage={data.usage} />
      <ForecastChart forecast={data.forecast} recs={data.recs} />
      <Recommendations recs={data.recs} />
    </main>
  );
}
