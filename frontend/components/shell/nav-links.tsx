"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ICON_SIZE, ICON_STROKE } from "@/lib/constants";
import { APP_NAV } from "@/lib/routes";
import { cn } from "@/lib/utils";
import { NAV_ICONS } from "./nav-icons";

interface NavLinksProps {
  labelClassName: string;
}

export function NavLinks({ labelClassName }: NavLinksProps) {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5">
      {APP_NAV.map((route) => {
        const Icon = NAV_ICONS[route.href];
        const isActive = pathname === route.href || pathname.startsWith(`${route.href}/`);
        return (
          <Link
            key={route.href}
            href={route.href}
            title={route.label}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "nav-link flex items-center gap-3 rounded-full px-3 py-2 text-sm transition-colors duration-150",
              isActive ? "text-accent" : "text-muted hover:text-foreground",
            )}
          >
            {Icon && <Icon size={ICON_SIZE} strokeWidth={ICON_STROKE} className="shrink-0" aria-hidden />}
            <span className={cn("truncate", labelClassName)}>{route.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
