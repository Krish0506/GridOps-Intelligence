/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#070d1a",
          900: "#0b1220",
          800: "#111c31",
          700: "#1a2942",
          600: "#243650",
        },
        ink: {
          900: "#101828",
          700: "#344054",
          500: "#667085",
          300: "#d0d5dd",
          100: "#f2f4f7",
          50: "#f8fafc",
        },
        teal: {
          50: "#ecfeff",
          100: "#cffafe",
          200: "#a5f3fc",
          300: "#67e8f9",
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
        },
        signal: {
          amber: "#f59e0b",
          "amber-soft": "#fffbeb",
          red: "#dc2626",
          "red-soft": "#fef2f2",
          green: "#059669",
          "green-soft": "#ecfdf5",
          blue: "#2563eb",
          "blue-soft": "#eff6ff",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,0.04), 0 8px 24px rgba(16,24,40,0.05)",
        float: "0 24px 60px rgba(7,13,26,0.24)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 240ms ease-out",
      },
    },
  },
  plugins: [],
};
