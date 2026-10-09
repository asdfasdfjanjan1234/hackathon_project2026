import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function LiveWattage() {
  const [reading, setReading] = useState(null);

  useEffect(() => {
    const poll = () => api.live().then(setReading).catch(() => {});
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="card">
      <h2>Live power</h2>
      <p className="big">{reading ? `${reading.watts} W` : "—"}</p>
      {reading?.simulated && <span className="tag estimated">simulated</span>}
      {reading && !reading.simulated && <span className="tag measured">{reading.source}</span>}
    </section>
  );
}
