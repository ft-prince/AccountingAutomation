import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";
import { LIGHT_TOKENS } from "./lib/tokens";

// PROJECT_SPECS §9 — the only permitted colours and fonts.
// shadcn/ui colour names (primary, card, popover, secondary, destructive, input, ring)
// are aliases onto those tokens via the CSS variables declared in app/globals.css.
const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: { 50: LIGHT_TOKENS["cream-50"], 100: LIGHT_TOKENS["cream-100"], 200: LIGHT_TOKENS["cream-200"] },
        accent: { DEFAULT: LIGHT_TOKENS.accent, 600: LIGHT_TOKENS["accent-600"], foreground: LIGHT_TOKENS["cream-50"] },
        ink: { DEFAULT: LIGHT_TOKENS.ink, muted: LIGHT_TOKENS["ink-muted"] },
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        info: "var(--info)",
        // theme-dependent surfaces, addressed via CSS variables so components stay theme-agnostic
        background: "var(--background)",
        surface: "var(--surface)",
        border: "var(--border)",
        foreground: "var(--foreground)",
        muted: { DEFAULT: "var(--muted)", foreground: "var(--muted)" },
        // shadcn aliases
        card: { DEFAULT: "var(--card)", foreground: "var(--card-foreground)" },
        popover: { DEFAULT: "var(--popover)", foreground: "var(--popover-foreground)" },
        primary: { DEFAULT: "var(--primary)", foreground: "var(--primary-foreground)" },
        secondary: { DEFAULT: "var(--secondary)", foreground: "var(--secondary-foreground)" },
        destructive: { DEFAULT: "var(--destructive)", foreground: "var(--destructive-foreground)" },
        input: "var(--input)",
        ring: "var(--ring)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
      },
      borderRadius: {
        card: "var(--radius)",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 6px)",
      },
      transitionDuration: { DEFAULT: "150ms" },
    },
  },
  plugins: [animate],
};
export default config;
