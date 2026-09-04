"use client";

import { CalendarClock, Plus } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/primitives/empty-state";
import { Field } from "@/components/primitives/field";
import { MoneyText } from "@/components/primitives/money-text";
import { NativeSelect } from "@/components/primitives/native-select";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Tabs } from "@/components/primitives/tabs";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useCreateFixedLine, useFixedLines, type FixedLineInput } from "@/lib/forecast";
import { formatDate } from "@/lib/format";
import { REPORT_NAMES } from "@/lib/reports";
import { useCreateReportSchedule, useReportSchedules, type ScheduleInput } from "@/lib/schedules";
import { toastApiError } from "@/lib/toast";
import type { FixedLineCadence, FixedLineDirection, ReportFormat, ReportScheduleCadence } from "@/lib/types";

type Section = "fixed-lines" | "schedules";
const SECTIONS = [
  { value: "fixed-lines", label: "Fixed lines" },
  { value: "schedules", label: "Report schedules" },
] as const;
const CADENCES: readonly FixedLineCadence[] = ["monthly", "quarterly", "yearly", "once"];
const DIRECTIONS: readonly FixedLineDirection[] = ["outflow", "inflow"];
const SCHEDULE_CADENCES: readonly ReportScheduleCadence[] = ["daily", "weekly", "monthly"];
const FORMATS: readonly ReportFormat[] = ["pdf", "xlsx"];
const MONEY_PATTERN = /^\d+(\.\d{1,2})?$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function FixedLineDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const create = useCreateFixedLine();
  const [form, setForm] = useState<FixedLineInput>({ name: "", amount: "", cadence: "monthly", next_date: "", direction: "outflow", is_active: true });
  const set = <K extends keyof FixedLineInput>(key: K, value: FixedLineInput[K]) => setForm((current) => ({ ...current, [key]: value }));
  const amountError = form.amount && !MONEY_PATTERN.test(form.amount) ? "Rupees with up to 2 decimals" : undefined;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add fixed line</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="fl-name" label="Name" required className="sm:col-span-2">
            <Input id="fl-name" value={form.name} onChange={(event) => set("name", event.target.value)} placeholder="Office rent" />
          </Field>
          <Field id="fl-amount" label="Amount (₹)" required error={amountError}>
            <Input id="fl-amount" inputMode="decimal" value={form.amount ?? ""} onChange={(event) => set("amount", event.target.value.trim())} />
          </Field>
          <Field id="fl-direction" label="Direction">
            <NativeSelect id="fl-direction" value={form.direction} onChange={(event) => set("direction", event.target.value as FixedLineDirection)}>
              {DIRECTIONS.map((direction) => (
                <option key={direction} value={direction}>{direction}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="fl-cadence" label="Cadence">
            <NativeSelect id="fl-cadence" value={form.cadence} onChange={(event) => set("cadence", event.target.value as FixedLineCadence)}>
              {CADENCES.map((cadence) => (
                <option key={cadence} value={cadence}>{cadence}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="fl-next" label="Next date" required>
            <Input id="fl-next" type="date" value={form.next_date} onChange={(event) => set("next_date", event.target.value)} />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!form.name || !form.amount || Boolean(amountError) || !form.next_date || create.isPending} onClick={() => create.mutate(form, { onSuccess: () => { toast({ title: "Fixed line added" }); onOpenChange(false); }, onError: (error) => toastApiError(error, "Could not add fixed line") })}>
            {create.isPending ? "Saving…" : "Add"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FixedLinesSection({ canEdit }: { canEdit: boolean }) {
  const lines = useFixedLines();
  const [isCreating, setIsCreating] = useState(false);
  return (
    <div className="space-y-3">
      {canEdit && (
        <Button onClick={() => setIsCreating(true)}>
          <Plus strokeWidth={ICON_STROKE} aria-hidden /> Add fixed line
        </Button>
      )}
      <QueryState isPending={lines.isPending} error={lines.error} onRetry={() => void lines.refetch()}>
        {lines.data?.length === 0 ? (
          <EmptyState icon={CalendarClock} title="No fixed lines" description="Rent, salaries, EMIs and statutory outflows the cashflow engine schedules deterministically (§8.2)." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Direction</TableHead>
                <TableHead>Cadence</TableHead>
                <TableHead>Next date</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.data?.map((line) => (
                <TableRow key={line.id}>
                  <TableCell className="font-medium">{line.name}</TableCell>
                  <TableCell><StatusBadge status={line.direction} tone={line.direction === "inflow" ? "success" : "danger"} /></TableCell>
                  <TableCell>{line.cadence}</TableCell>
                  <TableCell className="tabular-nums">{formatDate(line.next_date)}</TableCell>
                  <TableCell className="text-right"><MoneyText value={line.amount ?? "0"} /></TableCell>
                  <TableCell>{line.is_active === false ? <StatusBadge status="inactive" tone="muted" /> : <StatusBadge status="active" />}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
      {isCreating && <FixedLineDialog open onOpenChange={setIsCreating} />}
    </div>
  );
}

function ScheduleDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const create = useCreateReportSchedule();
  const [form, setForm] = useState<{ report: string; cadence: ReportScheduleCadence; format: ReportFormat; recipients: string }>({ report: "summary", cadence: "weekly", format: "pdf", recipients: "" });
  const recipients = form.recipients.split(/[\n,]/).map((value) => value.trim()).filter(Boolean);
  const invalid = recipients.find((value) => !EMAIL_PATTERN.test(value));
  const body: ScheduleInput = { report: form.report, params: {}, cadence: form.cadence, format: form.format, recipients };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New report schedule</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="rs-report" label="Report">
            <NativeSelect id="rs-report" value={form.report} onChange={(event) => setForm({ ...form, report: event.target.value })}>
              {REPORT_NAMES.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="rs-cadence" label="Cadence">
            <NativeSelect id="rs-cadence" value={form.cadence} onChange={(event) => setForm({ ...form, cadence: event.target.value as ReportScheduleCadence })}>
              {SCHEDULE_CADENCES.map((cadence) => (
                <option key={cadence} value={cadence}>{cadence}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="rs-format" label="Format">
            <NativeSelect id="rs-format" value={form.format} onChange={(event) => setForm({ ...form, format: event.target.value as ReportFormat })}>
              {FORMATS.map((format) => (
                <option key={format} value={format}>{format}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="rs-recipients" label="Recipients" required hint="Comma or newline separated" error={invalid ? `Not an email: ${invalid}` : undefined} className="sm:col-span-3">
            <Input id="rs-recipients" value={form.recipients} onChange={(event) => setForm({ ...form, recipients: event.target.value })} placeholder="cfo@example.com, ca@example.com" />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={recipients.length === 0 || Boolean(invalid) || create.isPending} onClick={() => create.mutate(body, { onSuccess: () => { toast({ title: "Schedule created" }); onOpenChange(false); }, onError: (error) => toastApiError(error, "Could not create schedule") })}>
            {create.isPending ? "Saving…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SchedulesSection({ canEdit }: { canEdit: boolean }) {
  const schedules = useReportSchedules();
  const [isCreating, setIsCreating] = useState(false);
  return (
    <div className="space-y-3">
      {canEdit && (
        <Button onClick={() => setIsCreating(true)}>
          <Plus strokeWidth={ICON_STROKE} aria-hidden /> New schedule
        </Button>
      )}
      <QueryState isPending={schedules.isPending} error={schedules.error} onRetry={() => void schedules.refetch()}>
        {schedules.data?.length === 0 ? (
          <EmptyState icon={CalendarClock} title="No scheduled reports" description="Fixed-content reports the org emails on a cadence (§7.3) — the only mail sent without a reviewer." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Report</TableHead>
                <TableHead>Cadence</TableHead>
                <TableHead>Format</TableHead>
                <TableHead>Recipients</TableHead>
                <TableHead>Last sent</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {schedules.data?.map((schedule) => (
                <TableRow key={schedule.id}>
                  <TableCell className="font-medium">{schedule.report}</TableCell>
                  <TableCell>{schedule.cadence}</TableCell>
                  <TableCell>{schedule.format}</TableCell>
                  <TableCell className="text-muted">{(schedule.recipients ?? []).join(", ")}</TableCell>
                  <TableCell className="tabular-nums">{schedule.last_sent_at ? formatDate(schedule.last_sent_at) : "never"}</TableCell>
                  <TableCell>{schedule.last_error ? <StatusBadge status="error" label={schedule.last_error} /> : <StatusBadge status={schedule.is_active === false ? "inactive" : "active"} />}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
      {isCreating && <ScheduleDialog open onOpenChange={setIsCreating} />}
    </div>
  );
}

/** §11 /settings forecast: fixed lines for the engine and §7.3 report schedules. */
export function ForecastTab({ canEdit }: { canEdit: boolean }) {
  const [section, setSection] = useState<Section>("fixed-lines");
  return (
    <div className="space-y-4">
      <Tabs items={SECTIONS} value={section} onChange={setSection} ariaLabel="Forecast settings" />
      {section === "fixed-lines" ? <FixedLinesSection canEdit={canEdit} /> : <SchedulesSection canEdit={canEdit} />}
    </div>
  );
}
