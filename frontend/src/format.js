export const peso = (n) =>
  `₱${Number(n).toLocaleString("en-PH", { maximumFractionDigits: 0 })}`;
