async function request(path, options) {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) {
    // The backend explains refused actions ("start the device reader first") in `error`.
    const body = await res.json().catch(() => null);
    throw new Error(body?.error || `${path} failed: ${res.status}`);
  }
  return res.json();
}

const get = (path) => request(path);
const post = (path, body) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
const del = (path) => request(path, { method: "DELETE" });

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
  if (params.carbonBudget != null) q.set("carbon_budget", params.carbonBudget);
  return `?${q}`;
}

export const api = {
  // range: "7d", "30d" or "month" (month to date).
  usage: (params, range = "30d") => {
    const q = billQuery(params);
    return get(`/usage${q ? `${q}&` : "?"}range=${range}`);
  },
  forecast: (params) => get(`/forecast${billQuery(params)}`),
  recommendations: (params) => get(`/recommendations${billQuery(params)}`),
  impact: (params) => get(`/impact${billQuery(params)}`),
  // CO₂ on this device and in cloud data centers, for the same windows as usage.
  carbon: (params, range = "30d") => {
    const q = billQuery(params);
    return get(`/carbon${q ? `${q}&` : "?"}range=${range}`);
  },
  models: (params) => get(`/models${billQuery(params)}`),

  live: () => get("/live"),
  system: () => get("/system"),

  // "Start reading my device": the local backend detects the OS, hardware and AI apps.
  startDevice: () => post("/device/start"),
  stopDevice: () => post("/device/stop"),
  deviceStatus: () => get("/device/status"),

  // Apply a recommendation to Ollama (unload, or switch to the smaller model).
  applyRecommendation: (rec) => post("/actions/apply", rec),

  // Wall-meter checks of the whole-machine reading.
  validation: () => get("/validation"),
  meterWatts: (value) => post("/validation/watts", { value }),
  meterStart: (value) => post("/validation/start", { value }),
  meterFinish: (value) => post("/validation/finish", { value }),
  deleteMeterCheck: (id) => del(`/validation/${id}`),
};
