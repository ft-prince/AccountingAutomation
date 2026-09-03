// PROJECT_SPECS §9 — the only permitted colours. Single source for tailwind.config.ts,
// globals.css documentation and the /dev/tokens verification page.
export const LIGHT_TOKENS = {
  "cream-50": "#FAF7F2",
  "cream-100": "#F5EFE6",
  "cream-200": "#EADFCF",
  accent: "#DE5D35",
  "accent-600": "#C24E2B",
  ink: "#161514",
  "ink-muted": "#635E59",
  success: "#2F7D4F",
  warning: "#B7791F",
  danger: "#B23A2E",
  info: "#2C5F8A",
} as const;

export const DARK_TOKENS = {
  background: "#161514",
  surface: "#1F1D1B",
  border: "#2C2925",
  text: "#F5EFE6",
  muted: "#A39E97",
  accent: "#DE5D35",
  success: "#4A9D6A",
  warning: "#D29A3A",
  danger: "#D25A4C",
  info: "#4A80AC",
} as const;

export type TokenName = keyof typeof LIGHT_TOKENS;
