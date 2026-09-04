"use client";

import { useState } from "react";
import { PartyCombobox } from "@/components/parties/party-combobox";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { useCreatePayment, type NewPayment } from "@/lib/payments";
import { todayIso } from "@/lib/periods";
import { toastApiError } from "@/lib/toast";
import type { Payment, PaymentMethod } from "@/lib/types";

const METHODS: readonly PaymentMethod[] = ["neft", "upi", "cheque", "card", "cash", "other"];
const MONEY_PATTERN = /^\d+(\.\d{1,2})?$/;

function emptyPayment(): NewPayment {
  return { party: "", direction: "received", amount: "", date: todayIso(), method: "neft", reference: "", notes: "" };
}

export interface RecordPaymentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pre-select a party (e.g. from the party page). */
  partyId?: string;
  onCreated?: (payment: Payment) => void;
}

export function RecordPaymentDialog({ open, onOpenChange, partyId, onCreated }: RecordPaymentDialogProps) {
  const [form, setForm] = useState<NewPayment>(() => ({ ...emptyPayment(), party: partyId ?? "" }));
  const create = useCreatePayment();
  const set = <K extends keyof NewPayment>(key: K, value: NewPayment[K]) => setForm((current) => ({ ...current, [key]: value }));

  const amountError = form.amount !== "" && !MONEY_PATTERN.test(form.amount) ? "Enter rupees with up to two decimals" : undefined;
  const isValid = form.party !== "" && form.amount !== "" && !amountError && form.date !== "";

  const submit = () =>
    create.mutate(form, {
      onSuccess: (payment) => {
        toast({ title: "Payment recorded", description: `${form.direction === "received" ? "Received" : "Paid"} ₹${form.amount}` });
        setForm({ ...emptyPayment(), party: partyId ?? "" });
        onOpenChange(false);
        onCreated?.(payment);
      },
      onError: (error) => toastApiError(error, "Could not record payment"),
    });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Record payment</DialogTitle>
          <DialogDescription>Amounts are stored as exact decimals; allocate to invoices afterwards.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="pay-party" label="Party" required className="sm:col-span-2">
            <PartyCombobox id="pay-party" value={form.party} onChange={(id) => set("party", id)} />
          </Field>
          <Field id="pay-direction" label="Direction" required>
            <NativeSelect id="pay-direction" value={form.direction} onChange={(event) => set("direction", event.target.value as NewPayment["direction"])}>
              <option value="received">Received (customer paid us)</option>
              <option value="made">Made (we paid a vendor)</option>
            </NativeSelect>
          </Field>
          <Field id="pay-amount" label="Amount (₹)" required error={amountError}>
            <Input id="pay-amount" inputMode="decimal" placeholder="0.00" value={form.amount} onChange={(event) => set("amount", event.target.value.trim())} />
          </Field>
          <Field id="pay-date" label="Date" required>
            <Input id="pay-date" type="date" value={form.date} onChange={(event) => set("date", event.target.value)} />
          </Field>
          <Field id="pay-method" label="Method">
            <NativeSelect id="pay-method" value={form.method} onChange={(event) => set("method", event.target.value as PaymentMethod)}>
              {METHODS.map((method) => (
                <option key={method} value={method}>
                  {method.toUpperCase()}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="pay-reference" label="Reference" hint="UTR, cheque number…">
            <Input id="pay-reference" value={form.reference} onChange={(event) => set("reference", event.target.value)} />
          </Field>
          <Field id="pay-notes" label="Notes">
            <Input id="pay-notes" value={form.notes ?? ""} onChange={(event) => set("notes", event.target.value)} />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={create.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!isValid || create.isPending}>
            {create.isPending ? "Saving…" : "Record payment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
