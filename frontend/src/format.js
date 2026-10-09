/**
 * Formatting utilities for AI Wattage Tracker
 */

export const peso = (n, decimals = 2) => {
  if (n === null || n === undefined || isNaN(n)) return "₱0.00";
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
  return `${Number(kwh).toFixed(decimals)} kWh`;
};

export const formatPercent = (pct, decimals = 1) => {
  if (pct === null || pct === undefined || isNaN(pct)) return "0%";
  return `${Number(pct).toFixed(decimals)}%`;
};
