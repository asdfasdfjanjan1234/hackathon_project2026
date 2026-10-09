/** @type {import('tailwindcss').Config} */

// Semantic colours come from CSS variables in App.css (light on :root, dark on .dark),
// stored as "R G B" so Tailwind's opacity modifiers (bg-accent/10) keep working.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      screens: {
        xs: '480px',
      },
      colors: {
        canvas: token('canvas'),
        surface: token('surface'),
        sunken: token('sunken'),
        line: token('line'),
        'line-strong': token('line-strong'),
        ink: {
          DEFAULT: token('ink'),
          soft: token('ink-soft'),
          muted: token('ink-muted'),
        },
        accent: {
          DEFAULT: token('accent'),
          on: token('on-accent'),
        },
        pos: token('pos'),
        warn: token('warn'),
        neg: token('neg'),
        viz: {
          blue: token('viz-blue'),
          violet: token('viz-violet'),
          amber: token('viz-amber'),
          green: token('viz-green'),
          red: token('viz-red'),
          grey: token('viz-grey'),
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        pop: 'var(--shadow-pop)',
      },
    },
  },
  plugins: [],
}
