import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "../theme";

const OPTIONS = [
  { id: "light", label: "Light", icon: Sun },
  { id: "system", label: "System", icon: Monitor },
  { id: "dark", label: "Dark", icon: Moon },
];

// Light / System / Dark. Icons only in the header; with labels in the mobile drawer.
export default function ThemeToggle({ showLabels = false, className = "" }) {
  const { preference, setPreference } = useTheme();

  return (
    <div className={`seg ${className}`} role="group" aria-label="Theme">
      {OPTIONS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => setPreference(id)}
          aria-pressed={preference === id}
          aria-label={`${label} theme`}
          title={`${label} theme`}
          className={`seg-item flex items-center justify-center gap-1.5 ${showLabels ? "flex-1" : "px-2"} ${
            preference === id ? "seg-item-active" : ""
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
          {showLabels && <span>{label}</span>}
        </button>
      ))}
    </div>
  );
}
