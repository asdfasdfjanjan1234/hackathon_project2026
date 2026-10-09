import { createContext, useCallback, useContext, useEffect, useState } from "react";

const STORAGE_KEY = "watttrace-theme";
const ThemeContext = createContext(null);
const darkQuery = () => window.matchMedia("(prefers-color-scheme: dark)");

const readPreference = () => {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
};

// preference: what the user picked ("system", "light", "dark"); resolved: what is showing.
export function ThemeProvider({ children }) {
  const [preference, setPreferenceState] = useState(readPreference);
  const [systemDark, setSystemDark] = useState(() => darkQuery().matches);
  const resolved = preference === "system" ? (systemDark ? "dark" : "light") : preference;

  useEffect(() => {
    const mq = darkQuery();
    const onChange = (e) => setSystemDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark");
  }, [resolved]);

  const setPreference = useCallback((value) => {
    setPreferenceState(value);
    try {
      if (value === "system") localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Private mode: the choice lasts for this session only
    }
  }, []);

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference }}>{children}</ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);

// A theme colour for SVG and inline styles (Recharts), e.g. color("viz-blue") or color("accent", 0.15).
// It reads the CSS variable, so charts follow the theme without re-rendering.
export const color = (name, alpha) => (alpha == null ? `rgb(var(--${name}))` : `rgb(var(--${name}) / ${alpha})`);
