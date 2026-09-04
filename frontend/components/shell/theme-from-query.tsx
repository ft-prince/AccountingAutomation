"use client";

import { useTheme } from "next-themes";
import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

const THEMES = ["light", "dark"] as const;

/** ?theme=light|dark on any app route — lets headless screenshot runs pin a theme. Mounted once in AppShell. */
export function ThemeFromQuery() {
  const { setTheme } = useTheme();
  const requested = useSearchParams().get("theme");
  useEffect(() => {
    if (THEMES.some((theme) => theme === requested)) setTheme(requested as (typeof THEMES)[number]);
  }, [requested, setTheme]);
  return null;
}
