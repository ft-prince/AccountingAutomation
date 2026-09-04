"use client";

import Big from "big.js";
import { Plus, Trash2 } from "lucide-react";
import { MoneyText } from "@/components/primitives/money-text";
import { usesIgst, type LineComputed, type SupplyType } from "@/components/review/recompute";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import type { InvoiceLineDraft, LineColumn } from "@/lib/invoice-draft";
import { cn } from "@/lib/utils";

interface Column {
  key: LineColumn;
  label: string;
  width: string;
  isNumeric: boolean;
}

// Same numeric-column style as the review screen's line table, without confidence or issue rows.
const COLUMNS: readonly Column[] = [
  { key: "description", label: "Description", width: "min-w-[12rem]", isNumeric: false },
  { key: "hsn_sac", label: "HSN/SAC", width: "w-20", isNumeric: false },
  { key: "quantity", label: "Qty", width: "w-16", isNumeric: true },
  { key: "uom", label: "UoM", width: "w-14", isNumeric: false },
  { key: "unit_price", label: "Unit price", width: "w-24", isNumeric: true },
  { key: "discount", label: "Discount", width: "w-20", isNumeric: true },
  { key: "rate", label: "Rate %", width: "w-16", isNumeric: true },
  { key: "cess_rate", label: "Cess %", width: "w-16", isNumeric: true },
];

const COMPUTED_COLUMN_COUNT = 5;

export interface NewInvoiceLinesProps {
  lines: readonly InvoiceLineDraft[];
  computed: readonly LineComputed[];
  supplyType: SupplyType;
  onChange: (index: number, column: LineColumn, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}

export function NewInvoiceLines({ lines, computed, supplyType, onChange, onAdd, onRemove }: NewInvoiceLinesProps) {
  const isIgst = usesIgst(supplyType);
  const columnCount = COLUMNS.length + COMPUTED_COLUMN_COUNT;
  return (
    <section aria-label="Line items" className="space-y-2">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[60rem] text-xs">
          <thead className="bg-background text-left text-muted">
            <tr>
              <th className="px-2 py-1.5 font-medium">#</th>
              {COLUMNS.map((column) => (
                <th key={column.key} className={cn("px-1 py-1.5 font-medium", column.width, column.isNumeric && "text-right")}>
                  {column.label}
                </th>
              ))}
              <th className="px-2 py-1.5 text-right font-medium">Taxable</th>
              <th className="px-2 py-1.5 text-right font-medium">{isIgst ? "IGST" : "CGST + SGST"}</th>
              <th className="px-2 py-1.5 text-right font-medium">Cess</th>
              <th className="px-2 py-1.5 text-right font-medium">Total</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => {
              const row = computed[index];
              return (
                <tr key={line.key} className="border-t border-border">
                  <td className="px-2 py-1 text-muted tabular-nums">{index + 1}</td>
                  {COLUMNS.map((column) => (
                    <td key={column.key} className="px-1 py-1">
                      <input
                        aria-label={`Line ${index + 1} ${column.label}`}
                        className={cn(
                          "h-8 w-full rounded-md border border-input bg-surface px-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                          column.isNumeric && "text-right tabular-nums",
                        )}
                        inputMode={column.isNumeric ? "decimal" : "text"}
                        value={line[column.key]}
                        onChange={(event) => onChange(index, column.key, event.target.value)}
                      />
                    </td>
                  ))}
                  <td className="px-2 py-1 text-right">{row && <MoneyText value={row.taxable_value} />}</td>
                  <td className="px-2 py-1 text-right">{row && <MoneyText value={isIgst ? row.igst : sumHeads(row)} />}</td>
                  <td className="px-2 py-1 text-right">{row && <MoneyText value={row.cess} />}</td>
                  <td className="px-2 py-1 text-right font-medium">{row && <MoneyText value={row.line_total} />}</td>
                  <td className="px-1 py-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Remove line ${index + 1}`} onClick={() => onRemove(index)}>
                      <Trash2 size={14} strokeWidth={ICON_STROKE} className="text-muted" />
                    </Button>
                  </td>
                </tr>
              );
            })}
            {lines.length === 0 && (
              <tr>
                <td colSpan={columnCount} className="px-3 py-4 text-center text-muted">
                  No line items. Add one to compute tax.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Button variant="outline" size="sm" onClick={onAdd}>
        <Plus /> Add line
      </Button>
    </section>
  );
}

function sumHeads(row: LineComputed): string {
  return new Big(row.cgst).plus(row.sgst).toFixed(2);
}
