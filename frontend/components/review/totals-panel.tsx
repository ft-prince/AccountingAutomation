"use client";

import Big from "big.js";
import { MoneyText } from "@/components/primitives/money-text";
import type { InvoiceDetail, ValidationIssue } from "@/lib/invoices";
import { cn } from "@/lib/utils";
import { IssueList } from "./issue-list";
import { type InvoiceTotals, sameAmount } from "./recompute";

const ROWS: readonly { key: keyof InvoiceTotals; label: string }[] = [
  { key: "taxable_value", label: "Taxable value" },
  { key: "cgst", label: "CGST" },
  { key: "sgst", label: "SGST" },
  { key: "igst", label: "IGST" },
  { key: "cess", label: "Cess" },
  { key: "round_off", label: "Round-off" },
  { key: "total", label: "Total" },
];

const ZERO = "0.00";

export function totalsFromInvoice(invoice: InvoiceDetail): InvoiceTotals {
  return {
    taxable_value: invoice.taxable_value ?? ZERO,
    cgst: invoice.cgst ?? ZERO,
    sgst: invoice.sgst ?? ZERO,
    igst: invoice.igst ?? ZERO,
    cess: invoice.cess ?? ZERO,
    round_off: invoice.round_off ?? ZERO,
    total: invoice.total ?? ZERO,
  };
}

export function totalsMatch(client: InvoiceTotals, server: InvoiceTotals): boolean {
  return ROWS.every((row) => sameAmount(client[row.key], server[row.key]));
}

/** |server − client| as a decimal string; strings in, string out. */
export function totalDifference(client: string, server: string): string {
  return new Big(server).minus(new Big(client)).abs().toFixed(2);
}

export interface TotalsPanelProps {
  client: InvoiceTotals;
  server: InvoiceTotals;
  isDirty: boolean;
  issues: readonly ValidationIssue[];
  onResolve: (issueId: string, note: string) => void;
  isReadOnly: boolean;
}

/** Client recompute (instant) beside the server's Decimal result (authoritative), with a danger strip when they disagree. */
export function TotalsPanel({ client, server, isDirty, issues, onResolve, isReadOnly }: TotalsPanelProps) {
  const isMismatch = !isDirty && !totalsMatch(client, server);
  return (
    <section aria-label="Totals" className="space-y-2">
      <table className="w-full text-sm">
        <thead className="text-xs text-muted">
          <tr>
            <th className="py-1 text-left font-medium">Totals</th>
            <th className="py-1 text-right font-medium">Client (preview)</th>
            <th className="py-1 text-right font-medium">Server</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => {
            const isRowMismatch = isMismatch && !sameAmount(client[row.key], server[row.key]);
            const isTotal = row.key === "total";
            return (
              <tr key={row.key} className={cn("border-t border-border", isTotal && "font-semibold")}>
                <td className="py-1">{row.label}</td>
                <td className={cn("py-1 text-right", isRowMismatch && "text-danger")}>
                  <MoneyText value={client[row.key]} />
                </td>
                <td className="py-1 text-right">
                  <MoneyText value={server[row.key]} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {isDirty && <p className="text-xs text-muted">Unsaved edits — the server column updates on save.</p>}
      {isMismatch && (
        <p role="status" data-testid="reconciliation-strip" className="rounded-md border border-danger px-3 py-2 text-xs text-danger">
          Client recompute differs from the server by <MoneyText value={totalDifference(client.total, server.total)} className="font-semibold" /> on the total. The server figure is
          authoritative; check the stated total and line arithmetic.
        </p>
      )}
      <IssueList issues={issues} onResolve={onResolve} isReadOnly={isReadOnly} />
    </section>
  );
}
