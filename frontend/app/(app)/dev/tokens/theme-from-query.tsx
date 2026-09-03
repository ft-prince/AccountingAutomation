"use client";

import { useTheme } from "next-themes";
import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

const THEMES = ["light", "dark"] as const;

/** /dev/tokens?theme=light|dark — lets headless screenshot runs pin a theme. Dev page only. */
export function ThemeFromQuery() {
  const { setTheme } = useTheme();
  const requested = useSearchParams().get("theme");
  useEffect(() => {
    if (THEMES.some((theme) => theme === requested)) setTheme(requested as (typeof THEMES)[number]);
  }, [requested, setTheme]);
  return null;
}
