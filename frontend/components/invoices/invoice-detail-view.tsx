"use client";

import Big from "big.js";
import { ArrowLeft, ClipboardCheck, FileText } from "lucide-react";
import Link from "next/link";
import { MoneyText } from "@/components/primitives/money-text";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ICON_STROKE } from "@/lib/constants";
import { fetchSignedFileUrl } from "@/lib/documents";
import { formatDate, humanize } from "@/lib/format";
import { useInvoiceDetail } from "@/lib/invoice-queries";
import { orZero } from "@/lib/money";
import { usePayments } from "@/lib/payments";
import { toastApiError } from "@/lib/toast";
import type { InvoiceDetail } from "@/lib/types";

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right tabular-nums">{children}</dd>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="rounded-card border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

async function openDocument(documentId: string) {
  try {
    const signed = await fetchSignedFileUrl(documentId);
    window.open(signed.url, "_blank", "noopener");
  } catch (error) {
    toastApiError(error, "Could not open the document");
  }
}

function hasDocument(invoice: InvoiceDetail): boolean {
  return Boolean(invoice.document) && invoice.document !== "None";
}

export function InvoiceDetailView({ id }: { id: string }) {
  const invoice = useInvoiceDetail(id);
  const payments = usePayments({ party: invoice.data?.party });
  const allocations = (payments.data?.results ?? []).flatMap((payment) =>
    payment.allocations.filter((allocation) => allocation.invoice === id).map((allocation) => ({ payment, allocation })),
  );

  return (
    <QueryState isPending={invoice.isPending} error={invoice.error} onRetry={() => invoice.refetch()} skeletonClassName="h-96 w-full">
      {invoice.data && (
        <div className="space-y-5">
          <Link href="/invoices" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground">
            <ArrowLeft size={14} strokeWidth={ICON_STROKE} aria-hidden /> Invoices
          </Link>
          <PageHeader
            title={invoice.data.invoice_number}
            description={
              <span className="flex flex-wrap items-center gap-2">
                <StatusBadge status={invoice.data.status} />
                <StatusBadge status={invoice.data.payment_status} />
                <StatusBadge status={invoice.data.validation_status} />
                <span>
                  {invoice.data.direction === "outward" ? "Sale to" : "Purchase from"}{" "}
                  <Link href={`/parties/${invoice.data.party}`} className="underline underline-offset-2 hover:text-accent">
                    {invoice.data.party_name}
                  </Link>
                </span>
              </span>
            }
            actions={
              <>
                {hasDocument(invoice.data) && (
                  <Button variant="outline" onClick={() => openDocument(invoice.data.document)}>
                    <FileText strokeWidth={ICON_STROKE} aria-hidden /> Open document
                  </Button>
                )}
                <Button asChild>
                  <Link href={`/review?invoice=${invoice.data.id}`}>
                    <ClipboardCheck strokeWidth={ICON_STROKE} aria-hidden /> Open in review
                  </Link>
                </Button>
              </>
            }
          />

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Details">
              <dl>
                <DetailRow label="Invoice date">{formatDate(invoice.data.invoice_date)}</DetailRow>
                <DetailRow label="Due date">{formatDate(invoice.data.due_date)}</DetailRow>
                <DetailRow label="FY · period">
                  {invoice.data.fy} · {invoice.data.period_month}
                </DetailRow>
                <DetailRow label="Supply type">{humanize(invoice.data.supply_type)}</DetailRow>
                <DetailRow label="Place of supply">{invoice.data.place_of_supply_state_code || "—"}</DetailRow>
                <DetailRow label="Reverse charge">{invoice.data.is_reverse_charge ? "Yes" : "No"}</DetailRow>
                <DetailRow label="IRN">{invoice.data.irn ? <span className="break-all font-mono text-xs">{invoice.data.irn}</span> : "—"}</DetailRow>
                <DetailRow label="ITC">{invoice.data.itc_eligible ? "Eligible" : `Blocked${invoice.data.itc_blocked_reason ? ` · ${invoice.data.itc_blocked_reason}` : ""}`}</DetailRow>
                <DetailRow label="Confidence">
                  {invoice.data.confidence ?? "—"}
                  {invoice.data.confidence_field && (
                    <span className="ml-2 text-xs text-muted">weakest · {invoice.data.confidence_field}</span>
                  )}
                </DetailRow>
                <DetailRow label="Reviewed">{invoice.data.reviewed_at ? formatDate(invoice.data.reviewed_at) : "—"}</DetailRow>
              </dl>
            </Card>
            <Card title="Amounts">
              <dl>
                <DetailRow label="Taxable value"><MoneyText value={orZero(invoice.data.taxable_value)} /></DetailRow>
                <DetailRow label="CGST"><MoneyText value={orZero(invoice.data.cgst)} /></DetailRow>
                <DetailRow label="SGST"><MoneyText value={orZero(invoice.data.sgst)} /></DetailRow>
                <DetailRow label="IGST"><MoneyText value={orZero(invoice.data.igst)} /></DetailRow>
                <DetailRow label="Cess"><MoneyText value={orZero(invoice.data.cess)} /></DetailRow>
                <DetailRow label="Round off"><MoneyText value={orZero(invoice.data.round_off)} /></DetailRow>
                <div className="my-1 border-t border-border" />
                <DetailRow label="Total"><MoneyText value={orZero(invoice.data.total)} className="font-semibold" /></DetailRow>
                <DetailRow label="Paid"><MoneyText value={orZero(invoice.data.amount_paid)} /></DetailRow>
                <DetailRow label="Outstanding"><MoneyText value={orZero(invoice.data.outstanding)} className={new Big(orZero(invoice.data.outstanding)).gt(0) ? "font-semibold text-warning" : "text-success"} /></DetailRow>
              </dl>
            </Card>
            <Card title={`Issues (${invoice.data.issues.length})`}>
              {invoice.data.issues.length === 0 ? (
                <p className="text-sm text-muted">No validation issues.</p>
              ) : (
                <ul className="space-y-2">
                  {invoice.data.issues.map((issue) => (
                    <li key={issue.id} className="rounded-md border border-border p-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{issue.code}</span>
                        <StatusBadge status={issue.resolved_at ? "resolved" : issue.severity} tone={issue.resolved_at ? "success" : issue.severity === "error" ? "danger" : "warning"} label={issue.resolved_at ? "Resolved" : humanize(issue.severity)} />
                      </div>
                      <p className="mt-1 text-muted">{issue.message}</p>
                      {issue.field && <p className="mt-0.5 text-xs text-muted">field · {issue.field}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card title={`Lines (${invoice.data.lines.length})`}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>HSN/SAC</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Unit price</TableHead>
                  <TableHead className="text-right">Taxable</TableHead>
                  <TableHead className="text-right">Rate</TableHead>
                  <TableHead className="text-right">Tax</TableHead>
                  <TableHead className="text-right">Line total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoice.data.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell className="tabular-nums">{line.line_no}</TableCell>
                    <TableCell className="max-w-md">{line.description || "—"}</TableCell>
                    <TableCell className="tabular-nums">{line.hsn_sac || "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{line.quantity ?? "—"} {line.uom}</TableCell>
                    <TableCell className="text-right"><MoneyText value={orZero(line.unit_price)} /></TableCell>
                    <TableCell className="text-right"><MoneyText value={orZero(line.taxable_value)} /></TableCell>
                    <TableCell className="text-right tabular-nums">{line.rate ?? "—"}%</TableCell>
                    <TableCell className="text-right"><MoneyText value={new Big(orZero(line.cgst)).plus(orZero(line.sgst)).plus(orZero(line.igst)).plus(orZero(line.cess)).toFixed(2)} /></TableCell>
                    <TableCell className="text-right"><MoneyText value={orZero(line.line_total)} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          <Card title={`Allocations (${allocations.length})`}>
            {allocations.length === 0 ? (
              <p className="text-sm text-muted">
                No payments allocated.{" "}
                <Link href="/payments" className="underline underline-offset-2 hover:text-accent">
                  Record or allocate one
                </Link>
                .
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Reference</TableHead>
                    <TableHead className="text-right">Payment</TableHead>
                    <TableHead className="text-right">Allocated here</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allocations.map(({ payment, allocation }) => (
                    <TableRow key={allocation.id}>
                      <TableCell className="tabular-nums">{formatDate(payment.date)}</TableCell>
                      <TableCell>{humanize(payment.method)}</TableCell>
                      <TableCell>{payment.reference || "—"}</TableCell>
                      <TableCell className="text-right"><MoneyText value={orZero(payment.amount)} /></TableCell>
                      <TableCell className="text-right"><MoneyText value={orZero(allocation.amount)} className="font-medium" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </div>
      )}
    </QueryState>
  );
}
