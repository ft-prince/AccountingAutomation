"use client";

import { MoneyText } from "@/components/primitives/money-text";
import { sameAmount, type InvoiceTotals } from "@/components/review/recompute";
import { totalDifference } from "@/components/review/totals-panel";
import { cn } from "@/lib/utils";

const ROWS: readonly { key: keyof InvoiceTotals; label: string }[] = [
  { key: "taxable_value", label: "Taxable value" },
  { key: "cgst", label: "CGST" },
  { key: "sgst", label: "SGST" },
  { key: "igst", label: "IGST" },
  { key: "cess", label: "Cess" },
  { key: "round_off", label: "Round-off" },
  { key: "total", label: "Total" },
];

export interface NewInvoiceTotalsProps {
  /** big.js recompute of the lines on screen — instant feedback only. */
  preview: InvoiceTotals;
  /** Figures the server returned after a successful save; null before that. */
  server: InvoiceTotals | null;
}

/** Client preview beside the server's Decimal result, with a danger strip when they disagree
 * (the same reconciliation the review screen shows). */
export function NewInvoiceTotals({ preview, server }: NewInvoiceTotalsProps) {
  const isMismatch = server !== null && !ROWS.every((row) => sameAmount(preview[row.key], server[row.key]));
  return (
    <section aria-label="Totals preview" className="space-y-2">
      <table className="w-full text-sm">
        <thead className="text-xs text-muted">
          <tr>
            <th className="py-1 text-left font-medium">Totals</th>
            <th className="py-1 text-right font-medium">Preview (client)</th>
            {server && <th className="py-1 text-right font-medium">Server (authoritative)</th>}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => {
            const isRowMismatch = isMismatch && server !== null && !sameAmount(preview[row.key], server[row.key]);
            return (
              <tr key={row.key} className={cn("border-t border-border", row.key === "total" && "font-semibold")}>
                <td className="py-1">{row.label}</td>
                <td className={cn("py-1 text-right", isRowMismatch && "text-danger")}>
                  <MoneyText value={preview[row.key]} />
                </td>
                {server && (
                  <td className="py-1 text-right">
                    <MoneyText value={server[row.key]} />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-xs text-muted">
        Preview only — computed in the browser from the lines above. The server recomputes every tax figure on save and its result is authoritative.
      </p>
      {isMismatch && server !== null && (
        <p role="status" data-testid="create-reconciliation-strip" className="rounded-md border border-danger px-3 py-2 text-xs text-danger">
          The preview differs from the server by <MoneyText value={totalDifference(preview.total, server.total)} className="font-semibold" /> on the total. The server figure is
          authoritative; check the line arithmetic before you confirm this invoice.
        </p>
      )}
    </section>
  );
}
