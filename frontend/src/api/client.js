async function get(path) {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  usage: () => get("/usage"),
  live: () => get("/live"),
  forecast: () => get("/forecast"),
  recommendations: () => get("/recommendations"),
  impact: () => get("/impact"),
};
