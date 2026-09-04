"use client";

import { useState } from "react";
import { Field } from "@/components/primitives/field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/primitives/checkbox";
import { toast } from "@/hooks/use-toast";
import { useSaveBankAccount, type BankAccountInput } from "@/lib/bank";
import { toastApiError } from "@/lib/toast";
import type { BankAccount } from "@/lib/types";

const EMPTY: BankAccountInput = { name: "", bank: "", masked_account: "", opening_balance: "0.00", opening_balance_date: null, is_active: true };

export function AccountDialog({ account, open, onOpenChange }: { account: BankAccount | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [form, setForm] = useState<BankAccountInput>(() => (account ? { name: account.name, bank: account.bank ?? "", masked_account: account.masked_account ?? "", opening_balance: account.opening_balance ?? "0.00", opening_balance_date: account.opening_balance_date ?? null, is_active: account.is_active ?? true } : EMPTY));
  const save = useSaveBankAccount();
  const set = <K extends keyof BankAccountInput>(key: K, value: BankAccountInput[K]) => setForm((current) => ({ ...current, [key]: value }));

  const submit = () =>
    save.mutate(
      { id: account?.id, body: form },
      {
        onSuccess: () => {
          toast({ title: account ? "Account updated" : "Account added" });
          onOpenChange(false);
        },
        onError: (error) => toastApiError(error, "Could not save account"),
      },
    );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{account ? "Edit account" : "Add bank account"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="acc-name" label="Name" required className="sm:col-span-2">
            <Input id="acc-name" value={form.name} onChange={(event) => set("name", event.target.value)} />
          </Field>
          <Field id="acc-bank" label="Bank">
            <Input id="acc-bank" value={form.bank ?? ""} onChange={(event) => set("bank", event.target.value)} />
          </Field>
          <Field id="acc-masked" label="Account (masked)" hint="Last digits only, e.g. XXXX4321">
            <Input id="acc-masked" value={form.masked_account ?? ""} onChange={(event) => set("masked_account", event.target.value)} />
          </Field>
          <Field id="acc-opening" label="Opening balance (₹)">
            <Input id="acc-opening" inputMode="decimal" value={form.opening_balance ?? ""} onChange={(event) => set("opening_balance", event.target.value.trim())} />
          </Field>
          <Field id="acc-opening-date" label="Opening balance date">
            <Input id="acc-opening-date" type="date" value={form.opening_balance_date ?? ""} onChange={(event) => set("opening_balance_date", event.target.value || null)} />
          </Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <Checkbox checked={form.is_active ?? true} onChange={(event) => set("is_active", event.target.checked)} /> Active
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={form.name.trim() === "" || save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
