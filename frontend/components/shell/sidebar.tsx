"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Me } from "@/lib/auth";
import { ICON_SIZE, ICON_STROKE } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { BrandMark } from "./brand-mark";
import { NavLinks } from "./nav-links";
import { OrgSwitcher } from "./org-switcher";
import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";

export type SidebarMode = "auto" | "expanded" | "collapsed";

interface SidebarProps {
  me: Me | undefined;
  mode: SidebarMode;
  onToggle: () => void;
}

// "auto" follows the breakpoint: icons below lg (1024px), full sidebar above.
const WIDTH: Record<SidebarMode, string> = { auto: "w-16 lg:w-60", expanded: "w-60", collapsed: "w-16" };
const LABEL: Record<SidebarMode, string> = { auto: "hidden lg:inline", expanded: "inline", collapsed: "hidden" };

export function Sidebar({ me, mode, onToggle }: SidebarProps) {
  const labelClassName = LABEL[mode];
  const isCollapsed = mode === "collapsed";
  return (
    <aside
      className={cn(
        "sticky top-0 flex h-screen shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-150",
        WIDTH[mode],
      )}
    >
      <div className="flex h-14 items-center justify-between px-3">
        <BrandMark name={me?.org?.brand_display_name} className={cn("px-2", labelClassName)} />
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {isCollapsed ? (
            <PanelLeftOpen size={ICON_SIZE} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
          ) : (
            <PanelLeftClose size={ICON_SIZE} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
          )}
        </Button>
      </div>

      {me && (
        <div className="px-2 pb-2">
          <OrgSwitcher me={me} labelClassName={labelClassName} />
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-2 py-2">
        <NavLinks labelClassName={labelClassName} />
      </div>

      <div className="flex flex-col gap-1 border-t border-border p-2">
        <ThemeToggle />
        {me && <UserMenu me={me} labelClassName={labelClassName} />}
      </div>
    </aside>
  );
}
