"use client";

import { LogOut, UserRound } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { type Me, useLogout } from "@/lib/auth";
import { ICON_SIZE, ICON_STROKE } from "@/lib/constants";
import { toastApiError } from "@/lib/toast";
import { cn } from "@/lib/utils";

interface UserMenuProps {
  me: Me;
  labelClassName: string;
}

export function UserMenu({ me, labelClassName }: UserMenuProps) {
  const logout = useLogout();
  const displayName = me.user.full_name || me.user.email;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex w-full items-center gap-3 rounded-full px-3 py-2 text-left text-sm hover:bg-secondary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        aria-label="Account menu"
      >
        <UserRound size={ICON_SIZE} strokeWidth={ICON_STROKE} className="shrink-0 text-muted" aria-hidden />
        <span className={cn("min-w-0 flex-1", labelClassName)}>
          <span className="block truncate">{displayName}</span>
          {me.role && <span className="block truncate text-xs text-muted">{me.role}</span>}
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel>
          <span className="block truncate text-sm">{displayName}</span>
          <span className="block truncate text-xs font-normal text-muted">{me.user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={logout.isPending}
          onSelect={() => logout.mutate(undefined, { onError: (error) => toastApiError(error) })}
        >
          <LogOut size={16} strokeWidth={ICON_STROKE} aria-hidden />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
