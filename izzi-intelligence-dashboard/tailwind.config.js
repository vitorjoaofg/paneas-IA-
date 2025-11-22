/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: "#05060a",
          foreground: "#f5f6fb",
        },
        accent: {
          DEFAULT: "#4e9eff",
          soft: "#84b7ff",
        },
        card: {
          DEFAULT: "rgba(26,29,35,0.65)",
          border: "rgba(255,255,255,0.06)",
        },
      },
      borderRadius: {
        "4xl": "2rem",
      },
      boxShadow: {
        glow: "0 10px 40px rgba(78, 158, 255, 0.15)",
      },
      backdropBlur: {
        xs: "2px",
      },
      fontFamily: {
        sans: ["'SF Pro Display'", "Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
