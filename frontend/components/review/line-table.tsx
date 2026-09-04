"use client";

import Big from "big.js";
import { Plus, Trash2 } from "lucide-react";
import { Fragment } from "react";
import { MoneyText } from "@/components/primitives/money-text";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import type { ValidationIssue } from "@/lib/invoices";
import { cn } from "@/lib/utils";
import { isLowConfidence } from "./confidence";
import { confidenceClass } from "./field";
import type { EditableLineColumn, LineDraft } from "./form-state";
import { IssueList } from "./issue-list";
import { lineIssues } from "./issue-map";
import { type LineComputed, type SupplyType, usesIgst } from "./recompute";

interface EditableColumn {
  key: EditableLineColumn;
  label: string;
  width: string;
  isNumeric: boolean;
}

const EDITABLE_COLUMNS: readonly EditableColumn[] = [
  { key: "description", label: "Description", width: "min-w-[12rem]", isNumeric: false },
  { key: "hsn_sac", label: "HSN/SAC", width: "w-20", isNumeric: false },
  { key: "quantity", label: "Qty", width: "w-16", isNumeric: true },
  { key: "uom", label: "UoM", width: "w-14", isNumeric: false },
  { key: "unit_price", label: "Unit price", width: "w-24", isNumeric: true },
  { key: "discount", label: "Discount", width: "w-20", isNumeric: true },
  { key: "rate", label: "Rate %", width: "w-16", isNumeric: true },
  { key: "cess_rate", label: "Cess %", width: "w-16", isNumeric: true },
];

const CELL_INPUT = "h-8 w-full rounded-md border border-input bg-surface px-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring read-only:opacity-70";

export interface LineTableProps {
  lines: readonly LineDraft[];
  computed: readonly LineComputed[];
  supplyType: SupplyType;
  issues: readonly ValidationIssue[];
  onChange: (index: number, column: EditableLineColumn, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onResolve: (issueId: string, note: string) => void;
  isReadOnly: boolean;
}

/** Editable line items with live client-side recompute (server figures are authoritative). */
export function LineTable({ lines, computed, supplyType, issues, onChange, onAdd, onRemove, onResolve, isReadOnly }: LineTableProps) {
  const isIgst = usesIgst(supplyType);
  const columnCount = EDITABLE_COLUMNS.length + 5;
  return (
    <section aria-label="Line items" className="space-y-2">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-xs">
          <thead className="bg-background text-left text-muted">
            <tr>
              <th className="px-2 py-1.5 font-medium">#</th>
              {EDITABLE_COLUMNS.map((column) => (
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
              const isLow = isLowConfidence(line.confidence);
              const rowIssues = lineIssues(issues, index);
              return (
                <Fragment key={line.key}>
                  <tr data-line={index} className={cn("border-t border-border", isLow && "border-l-2 border-l-accent")}>
                    <td className="px-2 py-1 text-muted tabular-nums">{index + 1}</td>
                    {EDITABLE_COLUMNS.map((column) => (
                      <td key={column.key} className="px-1 py-1">
                        <input
                          aria-label={`Line ${index + 1} ${column.label}`}
                          data-field={`lines.${index}.${column.key}`}
                          className={cn(CELL_INPUT, column.isNumeric && "text-right tabular-nums", confidenceClass(isLow))}
                          inputMode={column.isNumeric ? "decimal" : "text"}
                          value={line[column.key]}
                          onChange={(event) => onChange(index, column.key, event.target.value)}
                          readOnly={isReadOnly}
                        />
                      </td>
                    ))}
                    <td className="px-2 py-1 text-right">{row && <MoneyText value={row.taxable_value} />}</td>
                    <td className="px-2 py-1 text-right">{row && <MoneyText value={isIgst ? row.igst : sumHeads(row)} />}</td>
                    <td className="px-2 py-1 text-right">{row && <MoneyText value={row.cess} />}</td>
                    <td className="px-2 py-1 text-right font-medium">{row && <MoneyText value={row.line_total} />}</td>
                    <td className="px-1 py-1">
                      {!isReadOnly && (
                        <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Remove line ${index + 1}`} onClick={() => onRemove(index)}>
                          <Trash2 size={14} strokeWidth={ICON_STROKE} className="text-muted" />
                        </Button>
                      )}
                    </td>
                  </tr>
                  {rowIssues.length > 0 && (
                    <tr className="bg-background">
                      <td colSpan={columnCount} className="px-3 py-1">
                        <IssueList issues={rowIssues} onResolve={onResolve} isReadOnly={isReadOnly} />
                      </td>
                    </tr>
                  )}
                </Fragment>
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
      {!isReadOnly && (
        <Button variant="outline" size="sm" onClick={onAdd}>
          <Plus /> Add line
        </Button>
      )}
    </section>
  );
}

function sumHeads(row: LineComputed): string {
  return new Big(row.cgst).plus(row.sgst).toFixed(2);
}
