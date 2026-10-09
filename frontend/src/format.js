/**
 * Formatting utilities for AI Wattage Tracker
 */

export const peso = (n, decimals = 2) => {
  if (n === null || n === undefined || isNaN(n)) return "₱0.00";
  // Device-only AI use can cost fractions of a centavo; don't round it to zero.
  if (n > 0 && n < 0.01) return "<₱0.01";
  return `₱${Number(n).toLocaleString("en-PH", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
};

export const pesoCompact = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "₱0";
  return `₱${Number(n).toLocaleString("en-PH", {
    maximumFractionDigits: 0,
  })}`;
};

export const formatWatts = (w) => {
  if (w === null || w === undefined || isNaN(w)) return "—";
  const num = Number(w);
  if (num >= 1000) return `${(num / 1000).toFixed(2)} kW`;
  return `${num.toFixed(1)} W`;
};

export const formatKwh = (kwh, decimals = 2) => {
  if (kwh === null || kwh === undefined || isNaN(kwh)) return "0.00 kWh";
  if (kwh > 0 && kwh < 0.01) return `${(kwh * 1000).toFixed(kwh < 0.0001 ? 3 : 1)} Wh`;
  return `${Number(kwh).toFixed(decimals)} kWh`;
};

export const formatPercent = (pct, decimals = 1) => {
  if (pct === null || pct === undefined || isNaN(pct)) return "0%";
  return `${Number(pct).toFixed(decimals)}%`;
};

export const formatWh = (wh) => {
  if (wh === null || wh === undefined || isNaN(wh)) return "—";
  if (wh >= 1000) return `${(wh / 1000).toFixed(2)} kWh`;
  return `${Number(wh).toFixed(wh < 10 ? 2 : 0)} Wh`;
};

export const formatTokens = (n) => {
  if (!n) return "0";
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return String(n);
};

export const formatCo2 = (kg) => {
  if (kg === null || kg === undefined || isNaN(kg)) return "—";
  if (kg >= 1000) return `${(kg / 1000).toFixed(2)} t CO₂`;
  if (kg >= 1) return `${kg.toFixed(1)} kg CO₂`;
  if (kg > 0 && kg < 0.001) return "<1 g CO₂";
  return `${Math.round(kg * 1000)} g CO₂`;
};

// Duration from hours: "3.2 h", "14 min" or "40 s", for "= X of running an aircon".
export const formatDuration = (hours) => {
  if (hours === null || hours === undefined || isNaN(hours)) return "—";
  if (hours >= 1) return `${hours.toFixed(hours >= 10 ? 0 : 1)} h`;
  if (hours * 60 >= 1) return `${Math.round(hours * 60)} min`;
  return `${Math.max(1, Math.round(hours * 3600))} s`;
};

export const shortDate = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-PH", { month: "short", day: "numeric" });
};

// Watts with enough decimals for the fractions of a watt one AI app often draws.
export const formatAppWatts = (w) => {
  if (w === null || w === undefined || isNaN(w)) return "—";
  return Number(w) >= 10 ? formatWatts(w) : `${Number(w).toFixed(2)} W`;
};

export const formatMb = (mb) => {
  if (mb === null || mb === undefined || isNaN(mb)) return "—";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
};
