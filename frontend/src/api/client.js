async function request(path, options) {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

const get = (path) => request(path);
const post = (path, body) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

// The user's rate, bills and budget; the backend does all bill math with them.
function billQuery(params) {
  if (!params) return "";
  const q = new URLSearchParams({
    rate: params.rate,
    baseline_rate: params.rate,
    baseline_bill: params.baseline,
    current_bill: params.currentBill,
    budget: params.budget,
  });
  if (params.cycleStartDay) q.set("cycle_start_day", params.cycleStartDay);
  return `?${q}`;
}

export const api = {
  usage: (params) => get(`/usage${billQuery(params)}`),
  forecast: (params) => get(`/forecast${billQuery(params)}`),
  recommendations: (params) => get(`/recommendations${billQuery(params)}`),
  impact: (params) => get(`/impact${billQuery(params)}`),
  models: (params) => get(`/models${billQuery(params)}`),

  live: () => get("/live"),
  system: () => get("/system"),

  // "Start reading my device": the local backend detects the OS, hardware and AI apps.
  startDevice: () => post("/device/start"),
  stopDevice: () => post("/device/stop"),
  deviceStatus: () => get("/device/status"),
  setDataSource: (source) => post("/device/source", { source }),
};
