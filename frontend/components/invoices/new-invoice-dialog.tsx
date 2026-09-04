"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { PartyCombobox } from "@/components/parties/party-combobox";
import { Checkbox } from "@/components/primitives/checkbox";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { computeInvoice } from "@/components/review/recompute";
import { totalsFromInvoice } from "@/components/review/totals-panel";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { addLine, draftErrors, emptyDraft, removeLine, setLineValue, supplyTypeFor, toCreateBody, type InvoiceDraft, type LineColumn } from "@/lib/invoice-draft";
import { useCreateInvoice } from "@/lib/invoice-queries";
import { todayIso } from "@/lib/periods";
import { useGstins } from "@/lib/settings";
import { toastApiError } from "@/lib/toast";
import type { InvoiceDetail, InvoiceDirection } from "@/lib/types";
import { NewInvoiceLines } from "./new-invoice-lines";
import { NewInvoiceTotals } from "./new-invoice-totals";

const STATE_CODE_LENGTH = 2;

export interface NewInvoiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Manual invoice entry. Totals are never sent — the server recomputes and returns them. */
export function NewInvoiceDialog({ open, onOpenChange }: NewInvoiceDialogProps) {
  const [draft, setDraft] = useState<InvoiceDraft>(() => emptyDraft(todayIso()));
  const [lineCount, setLineCount] = useState(1);
  const [saved, setSaved] = useState<InvoiceDetail | null>(null);
  const gstins = useGstins();
  const create = useCreateInvoice();

  const profiles = gstins.data ?? [];
  const profileId = draft.gstin_profile || profiles.find((profile) => profile.is_default)?.id || profiles[0]?.id || "";
  const supplierState = profiles.find((profile) => profile.id === profileId)?.state_code ?? "";
  const supplyType = supplyTypeFor(supplierState, draft.place_of_supply_state_code);
  const preview = useMemo(() => computeInvoice(draft.lines, supplyType), [draft.lines, supplyType]);
  const errors = draftErrors(draft);

  const set = <K extends keyof InvoiceDraft>(key: K, value: InvoiceDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));

  const reset = () => {
    setDraft(emptyDraft(todayIso()));
    setLineCount(1);
    setSaved(null);
  };

  const close = () => {
    onOpenChange(false);
    reset();
  };

  const submit = () =>
    create.mutate(toCreateBody({ ...draft, gstin_profile: profileId }), {
      onSuccess: (invoice) => {
        setSaved(invoice);
        toast({ title: `Invoice ${invoice.invoice_number} created`, description: "Server totals are shown below." });
      },
      onError: (error) => toastApiError(error, "Could not create the invoice"),
    });

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New invoice</DialogTitle>
          <DialogDescription>
            Enter the header and lines. Tax below is a browser preview; the server recomputes every figure and its result is authoritative.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="new-invoice-party" label="Party" required className="sm:col-span-2">
            <PartyCombobox
              id="new-invoice-party"
              value={draft.party}
              onChange={(id, party) =>
                setDraft((current) => ({
                  ...current,
                  party: id,
                  place_of_supply_state_code: party?.state_code || current.place_of_supply_state_code,
                }))
              }
            />
          </Field>
          <Field id="new-invoice-direction" label="Direction" required>
            <NativeSelect id="new-invoice-direction" value={draft.direction} onChange={(event) => set("direction", event.target.value as InvoiceDirection)}>
              <option value="inward">Inward (purchase)</option>
              <option value="outward">Outward (sale)</option>
            </NativeSelect>
          </Field>
          <Field id="new-invoice-number" label="Invoice number" required>
            <Input id="new-invoice-number" value={draft.invoice_number} onChange={(event) => set("invoice_number", event.target.value)} maxLength={16} />
          </Field>
          <Field id="new-invoice-date" label="Invoice date" required>
            <Input id="new-invoice-date" type="date" value={draft.invoice_date} onChange={(event) => set("invoice_date", event.target.value)} />
          </Field>
          <Field id="new-invoice-due" label="Due date">
            <Input id="new-invoice-due" type="date" value={draft.due_date} onChange={(event) => set("due_date", event.target.value)} />
          </Field>
          <Field id="new-invoice-gstin" label="Our GSTIN" hint="Decides intra vs inter-state (§3.2).">
            <NativeSelect id="new-invoice-gstin" value={profileId} onChange={(event) => set("gstin_profile", event.target.value)}>
              {profiles.length === 0 && <option value="">No GSTIN profiles</option>}
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.gstin} · {profile.state_code}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="new-invoice-pos" label="Place of supply" hint="Two-digit state code, e.g. 27.">
            <Input
              id="new-invoice-pos"
              inputMode="numeric"
              maxLength={STATE_CODE_LENGTH}
              value={draft.place_of_supply_state_code}
              onChange={(event) => set("place_of_supply_state_code", event.target.value.trim())}
            />
          </Field>
          <Field id="new-invoice-irn" label="IRN">
            <Input id="new-invoice-irn" value={draft.irn} onChange={(event) => set("irn", event.target.value.trim())} />
          </Field>
          <Field id="new-invoice-terms" label="Payment terms">
            <Input id="new-invoice-terms" value={draft.payment_terms} onChange={(event) => set("payment_terms", event.target.value)} />
          </Field>
          <Field id="new-invoice-notes" label="Notes" className="sm:col-span-2">
            <Input id="new-invoice-notes" value={draft.notes} onChange={(event) => set("notes", event.target.value)} />
          </Field>
          <label className="flex items-end gap-2 pb-2 text-sm">
            <Checkbox checked={draft.is_reverse_charge} onChange={(event) => set("is_reverse_charge", event.target.checked)} /> Reverse charge
          </label>
        </div>

        <NewInvoiceLines
          lines={draft.lines}
          computed={preview.lines}
          supplyType={supplyType}
          onChange={(index, column: LineColumn, value) => setDraft((current) => setLineValue(current, index, column, value))}
          onAdd={() => {
            setDraft((current) => addLine(current, `line-${lineCount}`));
            setLineCount((count) => count + 1);
          }}
          onRemove={(index) => setDraft((current) => removeLine(current, index))}
        />

        <NewInvoiceTotals preview={preview.totals} server={saved ? totalsFromInvoice(saved) : null} />

        {errors.length > 0 && !saved && (
          <ul role="alert" className="space-y-0.5 text-xs text-danger">
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        )}

        {saved && (
          <p className="rounded-md border border-border px-3 py-2 text-xs">
            Saved as <span className="font-semibold">{saved.invoice_number}</span> with status {saved.status}.{" "}
            <Link href="/review" className="text-accent underline underline-offset-2" onClick={close}>
              Open the review queue
            </Link>
          </p>
        )}

        <DialogFooter>
          {saved ? (
            <>
              <Button variant="outline" onClick={reset}>
                Create another
              </Button>
              <Button onClick={close}>Done</Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={close} disabled={create.isPending}>
                Cancel
              </Button>
              <Button onClick={submit} disabled={errors.length > 0 || create.isPending}>
                {create.isPending ? "Saving…" : "Create invoice"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
