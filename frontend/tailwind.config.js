/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#0f172a",
        slate: "#1e293b",
        teal: "#14b8a6",
      },
    },
  },
  plugins: [],
};
