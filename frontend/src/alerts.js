// How each alert level from /api/alerts is shown: its tag class and label.
export const ALERT_LEVELS = {
  alert: { tag: "tech-tag-alert", label: "Alert" },
  warn: { tag: "tech-tag-sim", label: "Warning" },
  tip: { tag: "tech-tag-pos", label: "Saving" },
  info: { tag: "tech-tag-neutral", label: "Note" },
};

// Levels the assistant speaks up about by itself; notes stay in the bell.
export const SPEAK_UP_LEVELS = new Set(["alert", "warn", "tip"]);
