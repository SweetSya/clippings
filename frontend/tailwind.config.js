/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ember: {
          primary: "#C2410C",      // Terracotta
          "primary-hover": "#9A3412",
          accent: "#F59E0B",       // Amber
          neutral: "rgb(var(--c-muted) / <alpha-value>)",   // Stone (theme-aware)
          background: "rgb(var(--c-bg) / <alpha-value>)",   // Warm white / stone-950
          surface: "rgb(var(--c-surface) / <alpha-value>)",  // Off-white surface / stone-900
          "surface-raised": "rgb(var(--c-raised) / <alpha-value>)",
          "text-primary": "rgb(var(--c-text) / <alpha-value>)",
          "text-secondary": "rgb(var(--c-text-dim) / <alpha-value>)",
          border: "rgb(var(--c-border) / <alpha-value>)",
        }
      },
      fontFamily: {
        display: ["'Playfair Display'", "serif"],
        sans: ["'Source Sans 3'", "sans-serif"],
        mono: ["'Fira Code'", "monospace"],
      }
    },
  },
  plugins: [],
}
