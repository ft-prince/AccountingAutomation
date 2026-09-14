"use client";

import { ArrowLeft, GitMerge, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PaymentsTable } from "@/components/payments/payments-table";
import { AllocateDialog } from "@/components/payments/allocate-dialog";
import { RecordPaymentDialog } from "@/components/payments/record-payment-dialog";
import { ConfirmDialog } from "@/components/primitives/confirm-dialog";
import { MoneyText } from "@/components/primitives/money-text";
import { PageHeader } from "@/components/primitives/page-header";
import { RiskBandBadge } from "@/components/primitives/risk-band-badge";
import { QueryState } from "@/components/primitives/query-state";
import { StatTile } from "@/components/primitives/stat-tile";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Tabs } from "@/components/primitives/tabs";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useCustomerRisk } from "@/lib/forecast";
import { formatDate } from "@/lib/format";
import { EMPTY_INVOICE_FILTERS } from "@/lib/invoice-filters";
import { useInvoiceList } from "@/lib/invoice-queries";
import { formatINR, orZero } from "@/lib/money";
import { partyDisplayName, useMergeParty, useParty } from "@/lib/parties";
import { usePayments } from "@/lib/payments";
import { resolvePeriod, todayIso } from "@/lib/periods";
import { AGING_BUCKETS, useReport, type AgingRow } from "@/lib/reports";
import { toastApiError } from "@/lib/toast";
import type { Party, Payment } from "@/lib/types";
import { PartyCombobox } from "./party-combobox";
import { PartyDialog } from "./party-dialog";

type Tab = "invoices" | "payments";
const TABS = [
  { value: "invoices", label: "Invoices" },
  { value: "payments", label: "Payments" },
] as const;

function AgingCard({ title, row, asOf }: { title: string; row: AgingRow | undefined; asOf: string | undefined }) {
  return (
    <section aria-label={title} className="rounded-card border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold">{title}</h2>
      <p className="text-xs text-muted">{asOf ? `as of ${formatDate(asOf)}` : "—"}</p>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        {AGING_BUCKETS.map((bucket) => (
          <div key={bucket}>
            <dt className="text-xs text-muted">{bucket} d</dt>
            <dd><MoneyText value={row?.[bucket] ?? "0"} abbreviate className="font-medium" /></dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function PartyDetailView({ id }: { id: string }) {
  const router = useRouter();
  const party = useParty(id);
  const [tab, setTab] = useState<Tab>("invoices");
  const [isEditing, setIsEditing] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [mergeTarget, setMergeTarget] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [allocating, setAllocating] = useState<Payment | null>(null);
  const merge = useMergeParty();

  const period = resolvePeriod("fy_to_date", todayIso());
  const params = { from: period.from, to: period.to, basis: "accrual" as const };
  const isCustomer = party.data?.kind !== "vendor";
  const isVendor = party.data?.kind !== "customer";
  const arAging = useReport("ar-aging", params, isCustomer);
  const apAging = useReport("ap-aging", params, isVendor);
  const arRow = arAging.data?.rows.find((row) => row.party === id);
  const risk = useCustomerRisk(isCustomer);
  const riskRow = risk.data?.find((row) => row.party === id);
  const apRow = apAging.data?.rows.find((row) => row.party === id);

  const invoices = useInvoiceList({ ...EMPTY_INVOICE_FILTERS, party: id }, { pageSize: 50 });
  const payments = usePayments({ party: id });

  const runMerge = () =>
    merge.mutate(
      { sourceId: id, targetId: mergeTarget },
      {
        onSuccess: () => {
          toast({ title: "Merged", description: "Invoices and payments now point at the surviving party." });
          router.replace(`/parties/${mergeTarget}`);
        },
        onError: (error) => toastApiError(error, "Merge failed"),
      },
    );

  return (
    <QueryState isPending={party.isPending} error={party.error} onRetry={() => party.refetch()} skeletonClassName="h-96 w-full">
      {party.data && (
        <div className="space-y-5">
          <Link href="/parties" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground">
            <ArrowLeft size={14} strokeWidth={ICON_STROKE} aria-hidden /> Parties
          </Link>
          <PageHeader
            title={partyDisplayName(party.data)}
            description={
              <span className="flex flex-wrap items-center gap-2">
                <StatusBadge status={party.data.kind} tone={party.data.kind === "customer" ? "success" : party.data.kind === "vendor" ? "info" : "muted"} />
                {party.data.merged_into && <StatusBadge status="merged" tone="muted" label="Merged" />}
                {party.data.is_active === false && <StatusBadge status="inactive" tone="muted" label="Inactive" />}
                <span className="font-mono text-xs">{party.data.gstin || "no GSTIN"}</span>
                {party.data.primary_email && <span>· {party.data.primary_email}</span>}
                {party.data.payment_terms_days !== undefined && <span>· {party.data.payment_terms_days}-day terms</span>}
              </span>
            }
            actions={
              <>
                <Button variant="outline" onClick={() => setIsRecording(true)}>
                  <Plus strokeWidth={ICON_STROKE} aria-hidden /> Record payment
                </Button>
                <Button variant="outline" onClick={() => setIsEditing(true)}>
                  <Pencil strokeWidth={ICON_STROKE} aria-hidden /> Edit
                </Button>
                <Button variant="outline" onClick={() => setIsMerging(true)}>
                  <GitMerge strokeWidth={ICON_STROKE} aria-hidden /> Merge into…
                </Button>
              </>
            }
          />

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {isCustomer && <StatTile label="Receivable balance" value={arAging.data ? formatINR(arRow?.total ?? "0") : "…"} hint={arAging.data ? `as of ${formatDate(arAging.data.as_of)}` : undefined} />}
            {isVendor && <StatTile label="Payable balance" value={apAging.data ? formatINR(apRow?.total ?? "0") : "…"} hint={apAging.data ? `as of ${formatDate(apAging.data.as_of)}` : undefined} />}
            <StatTile label="Credit limit" value={party.data.credit_limit ? formatINR(party.data.credit_limit) : "—"} hint={party.data.credit_limit ? undefined : "not set"} />
            <div className="lift rounded-card border border-border bg-surface p-5">
              <p className="text-sm text-muted">Payment risk</p>
              <div className="mt-2"><RiskBandBadge band={riskRow?.band} /></div>
              <p className="mt-3 text-xs text-muted">{riskRow ? `score ${riskRow.score} · ${riskRow.drivers.join(" · ") || "no drivers"}` : isCustomer ? "not enough paid invoices to score" : "vendors are not scored"}</p>
            </div>
            <div className="lift rounded-card border border-border bg-surface p-5">
              <p className="text-sm text-muted">Email threads</p>
              <Link href={`/inbox?party=${id}`} className="mt-2 inline-block text-sm font-medium underline underline-offset-2 hover:text-accent">Open in Inbox</Link>
              <p className="mt-3 text-xs text-muted">Filtered to this party.</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {isCustomer && <AgingCard title="Receivables aging" row={arRow} asOf={arAging.data?.as_of} />}
            {isVendor && <AgingCard title="Payables aging" row={apRow} asOf={apAging.data?.as_of} />}
          </div>

          <Tabs items={TABS} value={tab} onChange={setTab} ariaLabel="Party records" />
          {tab === "invoices" ? (
            <QueryState isPending={invoices.isPending} error={invoices.error} onRetry={() => invoices.refetch()} skeletonClassName="h-64 w-full">
              <div className="rounded-card border border-border bg-surface">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Invoice</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Due</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead className="text-right">Outstanding</TableHead>
                      <TableHead>Payment</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invoices.data?.results.map((invoice) => (
                      <TableRow key={invoice.id} className="cursor-pointer" onClick={() => router.push(`/invoices/${invoice.id}`)}>
                        <TableCell className="font-medium">{invoice.invoice_number}</TableCell>
                        <TableCell className="tabular-nums">{formatDate(invoice.invoice_date)}</TableCell>
                        <TableCell className="tabular-nums">{formatDate(invoice.due_date)}</TableCell>
                        <TableCell>{invoice.direction === "outward" ? "Sale" : "Purchase"}</TableCell>
                        <TableCell className="text-right"><MoneyText value={orZero(invoice.total)} /></TableCell>
                        <TableCell className="text-right"><MoneyText value={orZero(invoice.outstanding)} /></TableCell>
                        <TableCell><StatusBadge status={invoice.payment_status} /></TableCell>
                        <TableCell><StatusBadge status={invoice.status} /></TableCell>
                      </TableRow>
                    ))}
                    {invoices.data?.results.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={8} className="py-8 text-center text-muted">No invoices for this party.</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
                {invoices.data?.next && (
                  <p className="border-t border-border px-4 py-2 text-xs text-muted">
                    Showing the latest 50 ·{" "}
                    <Link href={`/invoices?party=${id}`} className="underline underline-offset-2 hover:text-accent">
                      see all in Invoices
                    </Link>
                  </p>
                )}
              </div>
            </QueryState>
          ) : (
            <QueryState isPending={payments.isPending} error={payments.error} onRetry={() => payments.refetch()} skeletonClassName="h-64 w-full">
              <div className="rounded-card border border-border bg-surface">
                <PaymentsTable payments={payments.data?.results ?? []} onAllocate={setAllocating} />
              </div>
            </QueryState>
          )}

          {isEditing && <PartyDialog party={party.data} open onOpenChange={setIsEditing} />}
          <RecordPaymentDialog key={isRecording ? "open" : "closed"} open={isRecording} onOpenChange={setIsRecording} partyId={id} />
          <AllocateDialog payment={allocating} onOpenChange={(open) => !open && setAllocating(null)} />
          <ConfirmDialog
            open={isMerging}
            onOpenChange={(open) => {
              setIsMerging(open);
              if (!open) setMergeTarget("");
            }}
            title={`Merge ${partyDisplayName(party.data)} into…`}
            description="Every invoice, payment and email thread moves to the target party; this party is marked merged and hidden. This cannot be undone from the UI."
            confirmLabel="Merge"
            destructive
            isPending={merge.isPending}
            onConfirm={runMerge}
          >
            <PartyCombobox value={mergeTarget} onChange={(targetId) => setMergeTarget(targetId)} excludeId={id} placeholder="Search the surviving party…" />
            {mergeTarget === "" && <p className="text-xs text-muted">Pick the party that should survive.</p>}
          </ConfirmDialog>
        </div>
      )}
    </QueryState>
  );
}

export type { Party };
