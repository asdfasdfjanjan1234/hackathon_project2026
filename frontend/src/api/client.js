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

// A POST whose answer arrives bit by bit as NDJSON (one JSON event per line): onEvent gets each event.
async function stream(path, body, onEvent, signal) {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw Object.assign(new Error(err?.error || `${path} failed: ${res.status}`), { state: err?.state });
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, end).trim();
      buffer = buffer.slice(end + 1);
      if (line) onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}

// The user's rate, bills and budget; the backend does all bill math with them.
// dsd.
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
  if (params.tariff) q.set("tariff", params.tariff);
  // On a flat rate the backend estimates POP's rates from the regular rate, so they follow it.
  if (params.tariff === "pop") {
    q.set("peak_rate", params.peakRate);
    q.set("offpeak_rate", params.offpeakRate);
  }
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
  // Cheapest hours on the tariff, cleanest on the grid, and the best window for batch AI jobs.
  bestTime: (params) => get(`/best-time${billQuery(params)}`),

  live: () => get("/live"),
  system: () => get("/system"),

  // Budget overruns, savings and notes on the readings, most urgent first.
  alerts: (params, range = "30d") => {
    const q = billQuery(params);
    return get(`/alerts${q ? `${q}&` : "?"}range=${range}`);
  },

  // The local assistant (a small model in Ollama on this computer).
  assistantStatus: (params) => get(`/assistant/status${billQuery(params)}`),
  // body: {messages, view, range, brief}; onEvent gets {type: "delta" | "done" | "error", …}.
  assistantChat: (params, body, onEvent, signal) => stream(`/assistant/chat${billQuery(params)}`, body, onEvent, signal),
  assistantWarm: (params, body) => post(`/assistant/warm${billQuery(params)}`, body),
  assistantPull: (onEvent, signal) => stream("/assistant/pull", {}, onEvent, signal),

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
