"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { type Me, useSwitchOrg } from "@/lib/auth";
import { ICON_STROKE } from "@/lib/constants";
import { toastApiError } from "@/lib/toast";
import { cn } from "@/lib/utils";

interface OrgSwitcherProps {
  me: Me;
  labelClassName: string;
}

export function OrgSwitcher({ me, labelClassName }: OrgSwitcherProps) {
  const switchOrg = useSwitchOrg();
  const current = me.org;
  if (me.orgs.length === 0) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="lift flex w-full items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-left text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        aria-label="Switch organisation"
        disabled={switchOrg.isPending}
      >
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold">
          {(current?.name ?? "?").charAt(0).toUpperCase()}
        </span>
        <span className={cn("flex-1 truncate", labelClassName)}>{current?.name ?? "Select organisation"}</span>
        <ChevronsUpDown size={14} strokeWidth={ICON_STROKE} className={cn("text-muted", labelClassName)} aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel className="text-xs text-muted">Organisations</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {me.orgs.map((org) => (
          <DropdownMenuItem
            key={org.id}
            className="flex items-center justify-between"
            onSelect={() => {
              if (org.id !== current?.id) switchOrg.mutate(org.id, { onError: (error) => toastApiError(error) });
            }}
          >
            <span className="truncate">
              {org.name} <span className="text-xs text-muted">· {org.role}</span>
            </span>
            {org.id === current?.id && <Check size={14} strokeWidth={ICON_STROKE} className="text-accent" aria-hidden />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
