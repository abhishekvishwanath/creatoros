import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--canvas) / <alpha-value>)",
        "canvas-raised": "rgb(var(--canvas-raised) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        subtle: "rgb(var(--subtle) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        "accent-soft": "rgb(var(--accent-soft) / <alpha-value>)",
        "accent-ink": "rgb(var(--accent-ink) / <alpha-value>)",
        good: "rgb(var(--good) / <alpha-value>)",
        "good-soft": "rgb(var(--good-soft) / <alpha-value>)",
        warn: "rgb(var(--warn) / <alpha-value>)",
        "warn-soft": "rgb(var(--warn-soft) / <alpha-value>)",
        bad: "rgb(var(--bad) / <alpha-value>)",
        "bad-soft": "rgb(var(--bad-soft) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
        glow: "var(--shadow-glow)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
