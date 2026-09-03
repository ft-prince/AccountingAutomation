import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

// PROJECT_SPECS §9 — the only permitted colours and fonts.
const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: { 50: "#FAF7F2", 100: "#F5EFE6", 200: "#EADFCF" },
        accent: { DEFAULT: "#DE5D35", 600: "#C24E2B" },
        ink: { DEFAULT: "#161514", muted: "#635E59" },
        success: "#2F7D4F",
        warning: "#B7791F",
        danger: "#B23A2E",
        info: "#2C5F8A",
        // dark-theme surfaces, addressed via CSS variables so components stay theme-agnostic
        background: "var(--background)",
        surface: "var(--surface)",
        border: "var(--border)",
        foreground: "var(--foreground)",
        muted: "var(--muted)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
      },
      borderRadius: { card: "12px" },
      transitionDuration: { DEFAULT: "150ms" },
    },
  },
  plugins: [animate],
};
export default config;
