"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ICON_SIZE, ICON_STROKE } from "@/lib/constants";

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => setIsMounted(true), []);

  const isDark = isMounted && resolvedTheme === "dark";
  const Icon = isDark ? Sun : Moon;
  return (
    <Button
      variant="ghost"
      size="icon"
      className={className}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      <Icon size={ICON_SIZE} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
    </Button>
  );
}
