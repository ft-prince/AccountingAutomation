"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { DARK_TOKENS, LIGHT_TOKENS } from "@/lib/tokens";

// §9 chart rules: accent for the primary series, ink-muted at 40% for comparison, semantic green/red
// only for inflow/outflow. Everything here is derived from lib/tokens.ts; no other colour is permitted.
const ALPHA_40 = "66";
const ALPHA_12 = "1F";
const ACCENT_TINTS = ["FF", "CC", "99", "66", "40"] as const;

export interface ChartColors {
  accent: string;
  comparison: string;
  comparisonSolid: string;
  band: string;
  ink: string;
  muted: string;
  grid: string;
  surface: string;
  success: string;
  danger: string;
  /** Five accent tints + a muted "Other" for categorical slices (≤ 5 + Other). */
  categorical: readonly string[];
  /** Aging buckets 0-30 → 90+ deepen from light accent to solid. */
  aging: readonly string[];
}

function paletteFor(isDark: boolean): ChartColors {
  const accent = LIGHT_TOKENS.accent;
  const ink = isDark ? DARK_TOKENS.text : LIGHT_TOKENS.ink;
  const muted = isDark ? DARK_TOKENS.muted : LIGHT_TOKENS["ink-muted"];
  const tints = ACCENT_TINTS.map((alpha) => `${accent}${alpha}`);
  return {
    accent,
    comparison: `${muted}${ALPHA_40}`,
    comparisonSolid: muted,
    band: `${accent}${ALPHA_12}`,
    ink,
    muted,
    grid: isDark ? DARK_TOKENS.border : LIGHT_TOKENS["cream-200"],
    surface: isDark ? DARK_TOKENS.surface : LIGHT_TOKENS["cream-50"],
    success: isDark ? DARK_TOKENS.success : LIGHT_TOKENS.success,
    danger: isDark ? DARK_TOKENS.danger : LIGHT_TOKENS.danger,
    categorical: [...tints, `${muted}${ALPHA_40}`],
    aging: [tints[3], tints[2], tints[1], tints[0]],
  };
}

const LIGHT_PALETTE = paletteFor(false);
const DARK_PALETTE = paletteFor(true);

export function useChartColors(): ChartColors {
  const { resolvedTheme } = useTheme();
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => setIsMounted(true), []);
  return isMounted && resolvedTheme === "dark" ? DARK_PALETTE : LIGHT_PALETTE;
}
