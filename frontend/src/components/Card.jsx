import { Counter } from "../motion";

// The header every section card uses: title and subtitle on the left; tags, controls or a
// headline figure (children) on the right.
export function CardHeader({ title, sub, children, subHint }) {
  return (
    <div className="card-head">
      <div className="min-w-0">
        <h2 className="card-title">{title}</h2>
        {sub && (
          <div className="card-sub mt-0.5" title={subHint}>
            {sub}
          </div>
        )}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2 shrink-0 max-w-full">{children}</div>}
    </div>
  );
}

// A headline figure: label and icon, the value (counting to it when `format` is given), a
// line of context, and a footer with an optional status tag.
export function StatCard({
  title,
  icon: Icon,
  iconClass = "text-ink-muted",
  action,
  value,
  format,
  valueClass = "text-ink",
  sub,
  foot,
  tag,
  tagClass = "tech-tag-neutral",
}) {
  return (
    <div className="stat-card flex flex-col justify-between min-w-0 h-full">
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="eyebrow truncate">{title}</span>
          <span className="flex items-center gap-1 shrink-0">
            {action}
            {Icon && <Icon className={`w-4 h-4 ${iconClass}`} />}
          </span>
        </div>
        <div className={`stat-value truncate ${valueClass}`}>
          {format ? <Counter value={value} format={format} /> : value}
        </div>
        {sub && <div className="text-xs text-ink-muted mt-2 leading-snug">{sub}</div>}
      </div>
      {(foot || tag) && (
        <div className="mt-4 pt-3 border-t border-line flex items-center justify-between gap-2">
          <span className="min-w-0 text-xs leading-snug text-ink-soft">{foot}</span>
          {tag && <span className={`tech-tag shrink-0 ${tagClass}`}>{tag}</span>}
        </div>
      )}
    </div>
  );
}

// A small figure inside a card. `highlight` marks the one to act on with a green edge and dot,
// never a tinted fill behind coloured text.
export function MiniTile({ title, icon: Icon, value, sub, valueClass = "text-ink", highlight = false }) {
  return (
    <div className={`inset-panel p-3 min-w-0 ${highlight ? "border-pos/60" : ""}`}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-ink-muted min-w-0">
        {highlight && <span className="w-1.5 h-1.5 rounded-full bg-pos shrink-0" aria-hidden />}
        {Icon && <Icon className="w-3.5 h-3.5 shrink-0" />}
        <span className="truncate">{title}</span>
      </div>
      <div className={`text-base font-bold mt-0.5 tabular-nums ${valueClass}`}>{value}</div>
      {sub && <div className="text-xs text-ink-muted leading-snug mt-0.5">{sub}</div>}
    </div>
  );
}
