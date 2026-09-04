"use client";

import { Landmark, Plus } from "lucide-react";
import { useState } from "react";
import { Checkbox } from "@/components/primitives/checkbox";
import { EmptyState } from "@/components/primitives/empty-state";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useGstins, useSaveGstin, type GstinInput } from "@/lib/settings";
import { toastApiError } from "@/lib/toast";
import type { GstinProfile } from "@/lib/types";

type RegistrationType = NonNullable<GstinProfile["registration_type"]>;
const REGISTRATION_TYPES: readonly RegistrationType[] = ["regular", "composition", "casual", "sez", "unregistered"];
const GSTIN_PATTERN = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/; // §3.1 shape only; the server validates the checksum
const STATE_CODE_LENGTH = 2;

function fromProfile(profile: GstinProfile | null): GstinInput {
  return {
    gstin: profile?.gstin ?? "",
    state_code: profile?.state_code ?? "",
    trade_name: profile?.trade_name ?? "",
    registration_type: profile?.registration_type ?? "regular",
    is_default: profile?.is_default ?? false,
    valid_from: profile?.valid_from ?? null,
    valid_to: profile?.valid_to ?? null,
  };
}

function GstinDialog({ profile, open, onOpenChange }: { profile: GstinProfile | null; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [form, setForm] = useState<GstinInput>(() => fromProfile(profile));
  const save = useSaveGstin();
  const set = <K extends keyof GstinInput>(key: K, value: GstinInput[K]) => setForm((current) => ({ ...current, [key]: value }));
  const gstinError = form.gstin && !GSTIN_PATTERN.test(form.gstin) ? "15 characters: 2-digit state, PAN, entity, Z, check" : undefined;

  const submit = () =>
    save.mutate(
      { id: profile?.id, body: { ...form, state_code: form.state_code || form.gstin.slice(0, STATE_CODE_LENGTH), valid_from: form.valid_from || null, valid_to: form.valid_to || null } },
      {
        onSuccess: () => {
          toast({ title: profile ? "GSTIN updated" : "GSTIN added" });
          onOpenChange(false);
        },
        onError: (error) => toastApiError(error, "Could not save GSTIN"),
      },
    );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{profile ? "Edit GSTIN" : "Add GSTIN"}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="gstin-value" label="GSTIN" required error={gstinError} className="sm:col-span-2">
            <Input id="gstin-value" value={form.gstin} maxLength={15} disabled={Boolean(profile)} onChange={(event) => set("gstin", event.target.value.toUpperCase().trim())} />
          </Field>
          <Field id="gstin-trade" label="Trade name">
            <Input id="gstin-trade" value={form.trade_name ?? ""} onChange={(event) => set("trade_name", event.target.value)} />
          </Field>
          <Field id="gstin-type" label="Registration type">
            <NativeSelect id="gstin-type" value={form.registration_type} onChange={(event) => set("registration_type", event.target.value as RegistrationType)}>
              {REGISTRATION_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="gstin-from" label="Valid from">
            <Input id="gstin-from" type="date" value={form.valid_from ?? ""} onChange={(event) => set("valid_from", event.target.value || null)} />
          </Field>
          <Field id="gstin-to" label="Valid to">
            <Input id="gstin-to" type="date" value={form.valid_to ?? ""} onChange={(event) => set("valid_to", event.target.value || null)} />
          </Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <Checkbox checked={form.is_default ?? false} onChange={(event) => set("is_default", event.target.checked)} /> Default GSTIN for exports
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={form.gstin === "" || Boolean(gstinError) || save.isPending}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function GstinsTab({ canEdit }: { canEdit: boolean }) {
  const gstins = useGstins();
  const [editing, setEditing] = useState<{ profile: GstinProfile | null } | null>(null);

  return (
    <div className="space-y-4">
      {canEdit && (
        <Button onClick={() => setEditing({ profile: null })}>
          <Plus size={16} strokeWidth={ICON_STROKE} aria-hidden /> Add GSTIN
        </Button>
      )}
      <QueryState isPending={gstins.isPending} error={gstins.error} onRetry={() => void gstins.refetch()}>
        {gstins.data?.length === 0 ? (
          <EmptyState icon={Landmark} title="No GSTINs yet" description="Add the organisation's registrations; the default one is used on GSTR exports." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>GSTIN</TableHead>
                <TableHead>Trade name</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Valid</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {gstins.data?.map((profile) => (
                <TableRow key={profile.id}>
                  <TableCell className="font-mono text-xs">
                    {profile.gstin} {profile.is_default && <StatusBadge status="default" tone="info" label="default" />}
                  </TableCell>
                  <TableCell>{profile.trade_name}</TableCell>
                  <TableCell>{profile.state_code}</TableCell>
                  <TableCell>{profile.registration_type}</TableCell>
                  <TableCell className="text-muted">
                    {profile.valid_from ?? "—"} → {profile.valid_to ?? "open"}
                  </TableCell>
                  <TableCell className="text-right">
                    {canEdit && (
                      <Button variant="ghost" size="sm" onClick={() => setEditing({ profile })}>
                        Edit
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
      {editing && <GstinDialog key={editing.profile?.id ?? "new"} profile={editing.profile} open onOpenChange={(open) => !open && setEditing(null)} />}
    </div>
  );
}
