import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAFAF8",
        ink: {
          DEFAULT: "#191B1F",
          muted: "#5A5E67",
          faint: "#8B8F97",
        },
        line: "#E2E1DC",
        accent: {
          DEFAULT: "#1D2C4D",
          hover: "#141F38",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(25 27 31 / 0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
