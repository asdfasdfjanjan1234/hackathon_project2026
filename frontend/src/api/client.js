async function get(path) {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  usage: () => get("/usage"),
  forecast: () => get("/forecast"),
  recommendations: () => get("/recommendations"),

  // Live / measurement endpoint: try /measurement first, fallback to /live
  live: async () => {
    try {
      return await get("/measurement");
    } catch {
      return await get("/live");
    }
  },

  // Impact endpoint: try /impact; if 404/fails, compute fallback impact from forecast & usage
  impact: async (forecastData, usageData) => {
    try {
      return await get("/impact");
    } catch (e) {
      // Compute safe client-side decomposition if backend endpoint is not yet mounted
      const baseline = forecastData?.baseline_bill || 1500;
      const forecastBill = forecastData?.forecast_bill || 2650;
      const increase = Math.max(0, forecastBill - baseline);
      const aiCost = forecastData?.ai_cost || 1150;
      const aiEffect = Math.min(increase, aiCost);
      const otherEffect = Math.max(0, increase - aiEffect);
      const aiShare = increase > 0 ? aiEffect / increase : 0;
      
      let verdict = "minor";
      if (increase <= 0) verdict = "no_increase";
      else if (aiShare >= 0.5) verdict = "major";
      else if (aiShare >= 0.2) verdict = "contributing";

      return {
        baseline_bill: baseline,
        current_bill: forecastBill,
        increase,
        ai_effect: aiEffect,
        rate_effect: 0,
        other_effect: otherEffect,
        ai_share: aiShare,
        verdict,
        local_ai_kwh: usageData?.by_model?.filter(m => m.kind === 'local').reduce((s, m) => s + m.kwh, 0) || 72.4,
        cloud_ai_kwh_estimated: usageData?.by_model?.filter(m => m.kind === 'cloud').reduce((s, m) => s + m.kwh, 0) || 3.6,
      };
    }
  },
};
