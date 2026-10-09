import { color } from "../theme";

// The mark: a wattmeter dial with a bolt at its centre. The solid arc is the reading and the faint
// segment after the gap is the rest of the scale. Pass a title when the mark stands alone.
// public/logo-mark.svg is the same drawing with fixed colours, for the favicon.
export function LogoMark({ title, className = "" }) {
  const ink = color("on-brand");

  return (
    <svg
      viewBox="0 0 64 64"
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <rect width="64" height="64" rx="15" fill={color("brand")} />
      <g fill="none" stroke={ink} strokeWidth="5.6" strokeLinecap="round">
        <path d="M17.86 49.14A20 20 0 1 1 46.86 21.62" />
        <path d="M51.56 30.84A20 20 0 0 1 46.14 49.14" strokeOpacity="0.22" />
      </g>
      <polygon
        points="29.6,21.5 39,21.5 34.2,33 41.4,33 26.4,52 30.2,38.6 22.6,38.6"
        fill={ink}
        stroke={ink}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Mark and wordmark side by side.
export default function Logo({ className = "" }) {
  return (
    <span className={`flex items-center gap-2.5 min-w-0 ${className}`}>
      <LogoMark className="h-9 w-9 shrink-0" />
      <span className="text-xl leading-none font-bold tracking-tight text-ink whitespace-nowrap">
        Kilo <span className="font-medium text-ink-soft">What?</span>
      </span>
    </span>
  );
}
