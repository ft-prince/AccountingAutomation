"use client";

import { Pencil, Plus } from "lucide-react";
import { useState } from "react";
import { MoneyText } from "@/components/primitives/money-text";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { orZero } from "@/lib/money";
import type { BankAccount } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AccountDialog } from "./account-dialog";

export interface AccountsPanelProps {
  accounts: readonly BankAccount[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function AccountsPanel({ accounts, selectedId, onSelect }: AccountsPanelProps) {
  const [editing, setEditing] = useState<BankAccount | null | "new">(null);
  return (
    <section aria-label="Bank accounts" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Accounts</h2>
        <Button variant="outline" size="sm" onClick={() => setEditing("new")}>
          <Plus strokeWidth={ICON_STROKE} aria-hidden /> Add
        </Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {accounts.map((account) => (
          <div
            key={account.id}
            role="radio"
            aria-checked={account.id === selectedId}
            tabIndex={0}
            onClick={() => onSelect(account.id)}
            onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && onSelect(account.id)}
            className={cn("lift cursor-pointer rounded-card border bg-surface p-4", account.id === selectedId ? "border-accent" : "border-border")}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-medium">{account.name}</p>
                <p className="text-xs text-muted">
                  {account.bank || "—"} · {account.masked_account || "—"}
                </p>
              </div>
              <Button variant="ghost" size="icon" aria-label={`Edit ${account.name}`} onClick={(event) => {
                event.stopPropagation();
                setEditing(account);
              }}>
                <Pencil size={14} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted">Opening balance</p>
            <MoneyText value={orZero(account.opening_balance)} className="text-sm font-medium" />
            <p className="mt-1 text-xs text-muted">{account.opening_balance_date ? formatDate(account.opening_balance_date) : "no date"}</p>
            {!account.is_active && <StatusBadge status="inactive" tone="muted" label="Inactive" className="mt-2" />}
          </div>
        ))}
        {accounts.length === 0 && <p className="text-sm text-muted">No accounts yet. Add one to import statements.</p>}
      </div>
      {editing !== null && <AccountDialog key={editing === "new" ? "new" : editing.id} account={editing === "new" ? null : editing} open onOpenChange={(open) => !open && setEditing(null)} />}
    </section>
  );
}
