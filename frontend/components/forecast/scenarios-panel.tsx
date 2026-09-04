"use client";

import { Play, Plus, X } from "lucide-react";
import { useState } from "react";
import { PartyCombobox } from "@/components/parties/party-combobox";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { QueryState } from "@/components/primitives/query-state";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useCreateScenario, useRunScenario, useScenarios, type ScenarioOverride, type ScenarioRunResult } from "@/lib/forecast";
import { toastApiError } from "@/lib/toast";
import type { Scenario } from "@/lib/types";

type Kind = ScenarioOverride["kind"];
const KINDS: readonly { value: Kind; label: string }[] = [
  { value: "delay_customer", label: "Delay customer by N days" },
  { value: "lose_customer", label: "Lose customer" },
  { value: "delay_vendor", label: "Delay paying vendor by N days" },
  { value: "add_fixed_line", label: "Add a fixed line" },
  { value: "remove_fixed_line", label: "Remove a fixed line" },
  { value: "collection_policy_shift", label: "Change collection policy (± days)" },
  { value: "new_hire", label: "New hire (monthly outflow)" },
];
const MONEY_PATTERN = /^\d+(\.\d{1,2})?$/;

interface OverrideForm {
  kind: Kind;
  party: string;
  days: string;
  name: string;
  amount: string;
  date: string;
}
const EMPTY: OverrideForm = { kind: "delay_customer", party: "", days: "14", name: "", amount: "", date: "" };

/** Builds the exact §8.4 override object or returns a validation message. */
export function toOverride(form: OverrideForm): ScenarioOverride | string {
  const days = Number.parseInt(form.days, 10);
  switch (form.kind) {
    case "delay_customer":
    case "delay_vendor":
      if (!form.party) return "Pick a party";
      if (!Number.isInteger(days)) return "Days must be a whole number";
      return { kind: form.kind, party: form.party, days };
    case "lose_customer":
      return form.party ? { kind: "lose_customer", party: form.party } : "Pick a customer";
    case "add_fixed_line":
      if (!form.name) return "Name the line";
      if (!MONEY_PATTERN.test(form.amount)) return "Amount in rupees, up to 2 decimals";
      if (!form.date) return "Pick the first date";
      return { kind: "add_fixed_line", name: form.name, amount: form.amount, cadence: "monthly", next_date: form.date, direction: "outflow" };
    case "remove_fixed_line":
      return form.name ? { kind: "remove_fixed_line", name: form.name } : "Name the line to remove";
    case "collection_policy_shift":
      return Number.isInteger(days) ? { kind: "collection_policy_shift", days } : "Days must be a whole number (negative = collect sooner)";
    case "new_hire":
      if (!MONEY_PATTERN.test(form.amount)) return "Monthly cost in rupees";
      if (!form.date) return "Pick the start date";
      return { kind: "new_hire", amount: form.amount, start: form.date };
  }
}

function describe(override: ScenarioOverride): string {
  switch (override.kind) {
    case "delay_customer": return `delay customer ${override.days} d`;
    case "lose_customer": return "lose customer";
    case "delay_vendor": return `delay vendor ${override.days} d`;
    case "add_fixed_line": return `add ${override.name} ₹${override.amount}/${override.cadence}`;
    case "remove_fixed_line": return `remove ${override.name}`;
    case "collection_policy_shift": return `collection ${override.days > 0 ? "+" : ""}${override.days} d`;
    case "new_hire": return `new hire ₹${override.amount}/month from ${override.start}`;
  }
}

function overridesOf(scenario: Scenario): ScenarioOverride[] {
  return Array.isArray(scenario.overrides) ? (scenario.overrides as ScenarioOverride[]) : [];
}

function ScenarioDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const create = useCreateScenario();
  const [name, setName] = useState("");
  const [form, setForm] = useState<OverrideForm>(EMPTY);
  const [overrides, setOverrides] = useState<ScenarioOverride[]>([]);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof OverrideForm>(key: K, value: OverrideForm[K]) => setForm((current) => ({ ...current, [key]: value }));
  const needsParty = form.kind === "delay_customer" || form.kind === "lose_customer" || form.kind === "delay_vendor";
  const needsDays = form.kind === "delay_customer" || form.kind === "delay_vendor" || form.kind === "collection_policy_shift";
  const needsName = form.kind === "add_fixed_line" || form.kind === "remove_fixed_line";
  const needsAmount = form.kind === "add_fixed_line" || form.kind === "new_hire";
  const needsDate = form.kind === "add_fixed_line" || form.kind === "new_hire";

  const addOverride = () => {
    const result = toOverride(form);
    if (typeof result === "string") { setError(result); return; }
    setOverrides((current) => [...current, result]);
    setError(null);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New scenario</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4">
          <Field id="sc-name" label="Name" required>
            <Input id="sc-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Tata pays 30 days late" />
          </Field>
          <div className="grid gap-3 rounded-card border border-border p-3 sm:grid-cols-2">
            <Field id="sc-kind" label="Override" className="sm:col-span-2">
              <NativeSelect id="sc-kind" value={form.kind} onChange={(event) => set("kind", event.target.value as Kind)}>
                {KINDS.map((kind) => (
                  <option key={kind.value} value={kind.value}>{kind.label}</option>
                ))}
              </NativeSelect>
            </Field>
            {needsParty && (
              <Field id="sc-party" label="Party" className="sm:col-span-2">
                <PartyCombobox id="sc-party" value={form.party} onChange={(id) => set("party", id)} />
              </Field>
            )}
            {needsDays && (
              <Field id="sc-days" label="Days">
                <Input id="sc-days" inputMode="numeric" value={form.days} onChange={(event) => set("days", event.target.value)} />
              </Field>
            )}
            {needsName && (
              <Field id="sc-line" label="Fixed line name">
                <Input id="sc-line" value={form.name} onChange={(event) => set("name", event.target.value)} />
              </Field>
            )}
            {needsAmount && (
              <Field id="sc-amount" label="Amount (₹)">
                <Input id="sc-amount" inputMode="decimal" value={form.amount} onChange={(event) => set("amount", event.target.value.trim())} />
              </Field>
            )}
            {needsDate && (
              <Field id="sc-date" label="Date">
                <Input id="sc-date" type="date" value={form.date} onChange={(event) => set("date", event.target.value)} />
              </Field>
            )}
            <div className="sm:col-span-2">
              <Button type="button" variant="outline" size="sm" onClick={addOverride}>
                <Plus strokeWidth={ICON_STROKE} aria-hidden /> Add override
              </Button>
              {error && <p role="alert" className="mt-1 text-xs text-danger">{error}</p>}
            </div>
          </div>
          {overrides.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Overrides">
              {overrides.map((override, index) => (
                <li key={`${override.kind}-${index}`} className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs">
                  {describe(override)}
                  <button type="button" aria-label="Remove override" onClick={() => setOverrides((current) => current.filter((_, i) => i !== index))}>
                    <X size={12} strokeWidth={ICON_STROKE} aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!name || overrides.length === 0 || create.isPending} onClick={() => create.mutate({ name, overrides }, { onSuccess: () => { toast({ title: "Scenario saved" }); onOpenChange(false); }, onError: (err) => toastApiError(err, "Could not save scenario") })}>
            {create.isPending ? "Saving…" : "Save scenario"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export interface ScenariosPanelProps {
  canEdit: boolean;
  activeScenarioId: string | null;
  onOverlay: (scenario: Scenario | null, result: ScenarioRunResult | null) => void;
}

/** §8.4 scenarios: saved overrides re-run the engine and overlay P50 on the base chart. */
export function ScenariosPanel({ canEdit, activeScenarioId, onOverlay }: ScenariosPanelProps) {
  const scenarios = useScenarios();
  const run = useRunScenario();
  const [isCreating, setIsCreating] = useState(false);

  return (
    <section aria-label="Scenarios" className="rounded-card border border-border bg-surface p-5">
      <header className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Scenarios</h2>
          <p className="text-xs text-muted">Run one to overlay its P50 on the chart. Nothing is persisted by a run.</p>
        </div>
        {canEdit && (
          <Button variant="outline" size="sm" onClick={() => setIsCreating(true)}>
            <Plus strokeWidth={ICON_STROKE} aria-hidden /> New
          </Button>
        )}
      </header>
      <QueryState isPending={scenarios.isPending} error={scenarios.error} onRetry={() => void scenarios.refetch()} skeletonClassName="mt-3 h-24 w-full">
        {scenarios.data?.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No scenarios yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {scenarios.data?.map((scenario) => {
              const isActive = scenario.id === activeScenarioId;
              return (
                <li key={scenario.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                  <span className="min-w-0">
                    <span className="block font-medium">{scenario.name}</span>
                    <span className="block text-xs text-muted">{overridesOf(scenario).map(describe).join(" · ") || "no overrides"}</span>
                  </span>
                  {isActive ? (
                    <Button size="sm" variant="ghost" onClick={() => onOverlay(null, null)}>Clear overlay</Button>
                  ) : (
                    <Button size="sm" variant="outline" disabled={run.isPending} onClick={() => run.mutate(scenario.id, { onSuccess: (result) => onOverlay(scenario, result), onError: (error) => toastApiError(error, "Scenario run failed") })}>
                      <Play strokeWidth={ICON_STROKE} aria-hidden /> Run
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>
      {isCreating && <ScenarioDialog open onOpenChange={setIsCreating} />}
    </section>
  );
}
