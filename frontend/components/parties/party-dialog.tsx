"use client";

import { useState } from "react";
import { Checkbox } from "@/components/primitives/checkbox";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { useSaveParty, type PartyInput } from "@/lib/parties";
import { toastApiError } from "@/lib/toast";
import type { Party, PartyKind } from "@/lib/types";

const KINDS: readonly PartyKind[] = ["customer", "vendor", "both"];
const GSTIN_PATTERN = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/; // §3.1 shape only; the server validates the checksum
const DEFAULT_TERMS_DAYS = 30;

function fromParty(party: Party | null): PartyInput {
  return {
    legal_name: party?.legal_name ?? "",
    display_name: party?.display_name ?? "",
    kind: party?.kind ?? "customer",
    gstin: party?.gstin ?? "",
    state_code: party?.state_code ?? "",
    pan: party?.pan ?? "",
    primary_email: party?.primary_email ?? "",
    payment_terms_days: party?.payment_terms_days ?? DEFAULT_TERMS_DAYS,
    credit_limit: party?.credit_limit ?? null,
    is_composition: party?.is_composition ?? false,
    is_active: party?.is_active ?? true,
  };
}

export function PartyDialog({ party, open, onOpenChange, onSaved }: { party: Party | null; open: boolean; onOpenChange: (open: boolean) => void; onSaved?: (party: Party) => void }) {
  const [form, setForm] = useState<PartyInput>(() => fromParty(party));
  const save = useSaveParty();
  const set = <K extends keyof PartyInput>(key: K, value: PartyInput[K]) => setForm((current) => ({ ...current, [key]: value }));
  const gstinError = form.gstin && !GSTIN_PATTERN.test(form.gstin) ? "15 characters: 2-digit state, PAN, entity, Z, check" : undefined;

  const submit = () =>
    save.mutate(
      { id: party?.id, body: { ...form, gstin: form.gstin || null, state_code: form.state_code || form.gstin?.slice(0, 2) || "" } },
      {
        onSuccess: (saved) => {
          toast({ title: party ? "Party updated" : "Party created" });
          onOpenChange(false);
          onSaved?.(saved);
        },
        onError: (error) => toastApiError(error, "Could not save party"),
      },
    );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{party ? "Edit party" : "New party"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="party-legal" label="Legal name" required className="sm:col-span-2">
            <Input id="party-legal" value={form.legal_name} onChange={(event) => set("legal_name", event.target.value)} />
          </Field>
          <Field id="party-display" label="Display name">
            <Input id="party-display" value={form.display_name ?? ""} onChange={(event) => set("display_name", event.target.value)} />
          </Field>
          <Field id="party-kind" label="Kind" required>
            <NativeSelect id="party-kind" value={form.kind} onChange={(event) => set("kind", event.target.value as PartyKind)}>
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {kind}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="party-gstin" label="GSTIN" error={gstinError}>
            <Input id="party-gstin" value={form.gstin ?? ""} onChange={(event) => set("gstin", event.target.value.toUpperCase().trim())} maxLength={15} />
          </Field>
          <Field id="party-pan" label="PAN">
            <Input id="party-pan" value={form.pan ?? ""} onChange={(event) => set("pan", event.target.value.toUpperCase().trim())} maxLength={10} />
          </Field>
          <Field id="party-email" label="Primary email">
            <Input id="party-email" type="email" value={form.primary_email ?? ""} onChange={(event) => set("primary_email", event.target.value)} />
          </Field>
          <Field id="party-terms" label="Payment terms (days)">
            <Input id="party-terms" type="number" min={0} value={form.payment_terms_days ?? DEFAULT_TERMS_DAYS} onChange={(event) => set("payment_terms_days", Number(event.target.value))} />
          </Field>
          <Field id="party-credit" label="Credit limit (₹)">
            <Input id="party-credit" inputMode="decimal" value={form.credit_limit ?? ""} onChange={(event) => set("credit_limit", event.target.value.trim() || null)} />
          </Field>
          <div className="flex flex-col gap-2 text-sm">
            <label className="flex items-center gap-2">
              <Checkbox checked={form.is_composition ?? false} onChange={(event) => set("is_composition", event.target.checked)} /> Composition dealer
            </label>
            <label className="flex items-center gap-2">
              <Checkbox checked={form.is_active ?? true} onChange={(event) => set("is_active", event.target.checked)} /> Active
            </label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={form.legal_name.trim() === "" || Boolean(gstinError) || save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
