"use client";

import { useState } from "react";
import { Field } from "@/components/primitives/field";
import { QueryState } from "@/components/primitives/query-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import type { MeOrg } from "@/lib/auth";
import { useOrg, useUpdateOrg, type OrgInput } from "@/lib/settings";
import { toastApiError } from "@/lib/toast";

const PAN_PATTERN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;

function OrgForm({ org, canEdit }: { org: MeOrg; canEdit: boolean }) {
  const [form, setForm] = useState<OrgInput>({ name: org.name, legal_name: org.legal_name, pan: org.pan, brand_display_name: org.brand_display_name });
  const update = useUpdateOrg();
  const set = (key: keyof OrgInput, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const panError = form.pan && !PAN_PATTERN.test(form.pan) ? "10 characters: AAAAA9999A" : undefined;
  const isDirty = (Object.keys(form) as (keyof OrgInput)[]).some((key) => form[key] !== org[key]);

  const submit = () =>
    update.mutate(form, {
      onSuccess: () => toast({ title: "Organisation saved" }),
      onError: (error) => toastApiError(error, "Could not save organisation"),
    });

  return (
    <div className="max-w-xl space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="org-name" label="Name" required>
          <Input id="org-name" value={form.name} disabled={!canEdit} onChange={(event) => set("name", event.target.value)} />
        </Field>
        <Field id="org-brand" label="Brand display name" hint="Shown in the sidebar and on outbound mail.">
          <Input id="org-brand" value={form.brand_display_name} disabled={!canEdit} onChange={(event) => set("brand_display_name", event.target.value)} />
        </Field>
        <Field id="org-legal" label="Legal name">
          <Input id="org-legal" value={form.legal_name} disabled={!canEdit} onChange={(event) => set("legal_name", event.target.value)} />
        </Field>
        <Field id="org-pan" label="PAN" error={panError}>
          <Input id="org-pan" value={form.pan} maxLength={10} disabled={!canEdit} onChange={(event) => set("pan", event.target.value.toUpperCase().trim())} />
        </Field>
      </div>
      <p className="text-xs text-muted">AATO bracket: {org.aato_bracket.replaceAll("_", " ")} (derived from confirmed turnover).</p>
      {canEdit && (
        <Button onClick={submit} disabled={!isDirty || Boolean(panError) || form.name.trim() === "" || update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
        </Button>
      )}
    </div>
  );
}

export function OrgTab({ canEdit }: { canEdit: boolean }) {
  const org = useOrg();
  return (
    <QueryState isPending={org.isPending} error={org.error} onRetry={() => void org.refetch()}>
      {org.data && <OrgForm key={org.data.id} org={org.data} canEdit={canEdit} />}
    </QueryState>
  );
}
