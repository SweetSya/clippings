/** @type {import('tailwindcss').Config} */
export default {
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
          neutral: "#78716C",      // Stone
          background: "#FAFAF9",   // Warm white
          surface: "#F5F5F4",      // Off-white surface
          "surface-raised": "#E7E5E4",
          "text-primary": "#1C1917",
          "text-secondary": "#57534E",
          border: "#D6D3D1",
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
