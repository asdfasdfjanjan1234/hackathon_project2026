// An amount with its unit: ₱1,234.50, 2,270 Wh, 35%, 4.2 kg. A bare number ("Opus 5.5") is left alone.
const AMOUNT = /(<?₱\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:%|kWh|Wh|kW|W|kg|g)(?![A-Za-z]))/;

// A sentence with its amounts in bold, so the figures stand out in a paragraph of advice.
export default function Figures({ text }) {
  if (!text) return null;
  return String(text)
    .split(AMOUNT)
    .map((part, i) =>
      i % 2 ? (
        <strong key={i} className="whitespace-nowrap font-semibold text-ink tabular-nums">
          {part}
        </strong>
      ) : (
        part
      )
    );
}
