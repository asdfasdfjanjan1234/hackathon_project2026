/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Deep industrial telemetry palette (Asphalt / Slate / Steel)
        darkBg: '#090C12',
        panelBg: '#0E131E',
        cardBg: '#121927',
        cardHover: '#162032',
        cardBorder: 'rgba(255, 255, 255, 0.08)',
        cardBorderHover: 'rgba(56, 189, 248, 0.35)',
        
        // Precision instrumentation accents
        instrument: {
          cyan: '#38BDF8',     // Primary telemetry readout
          blue: '#0284C7',     // Grid data line
          emerald: '#10B981',  // Efficient / Optimized load
          amber: '#F59E0B',    // Load warning / Shift
          crimson: '#F43F5E',  // Over-budget / High draw
          slate: '#64748B',    // Baseline reference
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        instrument: '0 2px 12px -2px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.06)',
        instrumentHover: '0 8px 24px -4px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(56, 189, 248, 0.3), 0 0 20px -6px rgba(56, 189, 248, 0.15)',
      },
    },
  },
  plugins: [],
}
