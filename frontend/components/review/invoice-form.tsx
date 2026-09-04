"use client";

import { Input } from "@/components/ui/input";
import type { ValidationIssue } from "@/lib/invoices";
import { cn } from "@/lib/utils";
import { confidenceClass, ReviewField } from "./field";
import type { HeaderDraft } from "./form-state";
import { headerIssues, type HeaderFieldName } from "./issue-map";
import type { SupplyType } from "./recompute";

export const SUPPLY_TYPES: readonly { value: SupplyType; label: string }[] = [
  { value: "intra", label: "Intra-state (CGST + SGST)" },
  { value: "inter", label: "Inter-state (IGST)" },
  { value: "export", label: "Export" },
  { value: "sez", label: "SEZ" },
  { value: "import", label: "Import" },
];

export const SELECT_CLASS =
  "flex h-9 w-full rounded-md border border-input bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

export interface InvoiceFormProps {
  header: HeaderDraft;
  isLowConfidence: boolean;
  issues: readonly ValidationIssue[];
  onChange: (field: HeaderFieldName, value: string | boolean) => void;
  onResolve: (issueId: string, note: string) => void;
  isReadOnly: boolean;
}

/** Header fields of the invoice. Every control carries data-field so the screen can focus the first weak one. */
export function InvoiceForm({ header, isLowConfidence, issues, onChange, onResolve, isReadOnly }: InvoiceFormProps) {
  const lowClass = confidenceClass(isLowConfidence);
  const text = (field: HeaderFieldName, label: string, extra: { type?: string; placeholder?: string; className?: string } = {}) => (
    <ReviewField id={`f-${field}`} label={label} issues={headerIssues(issues, field)} onResolve={onResolve} isReadOnly={isReadOnly} className={extra.className}>
      <Input
        id={`f-${field}`}
        data-field={field}
        type={extra.type ?? "text"}
        placeholder={extra.placeholder}
        className={cn("h-9", lowClass)}
        value={String(header[field])}
        onChange={(event) => onChange(field, event.target.value)}
        readOnly={isReadOnly}
      />
    </ReviewField>
  );
  const checkbox = (field: "is_reverse_charge" | "has_qr" | "itc_eligible", label: string) => (
    <label className="flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        data-field={field}
        className="h-4 w-4 accent-accent"
        checked={Boolean(header[field])}
        onChange={(event) => onChange(field, event.target.checked)}
        disabled={isReadOnly}
      />
      {label}
    </label>
  );

  return (
    <section aria-label="Invoice header" className="grid grid-cols-2 gap-x-4 gap-y-3 md:grid-cols-3">
      {text("invoice_number", "Invoice number")}
      {text("invoice_date", "Invoice date", { type: "date" })}
      {text("due_date", "Due date", { type: "date" })}
      <ReviewField id="f-supply_type" label="Supply type" issues={headerIssues(issues, "supply_type")} onResolve={onResolve} isReadOnly={isReadOnly}>
        <select
          id="f-supply_type"
          data-field="supply_type"
          className={cn(SELECT_CLASS, lowClass)}
          value={header.supply_type}
          onChange={(event) => onChange("supply_type", event.target.value)}
          disabled={isReadOnly}
        >
          {SUPPLY_TYPES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </ReviewField>
      {text("place_of_supply_state_code", "Place of supply (state code)", { placeholder: "27" })}
      {text("irn", "IRN", { placeholder: "64-char e-invoice reference" })}
      <div className="col-span-2 flex flex-wrap gap-x-6 gap-y-2 md:col-span-3">
        {checkbox("is_reverse_charge", "Reverse charge")}
        {checkbox("has_qr", "Has signed QR")}
        {checkbox("itc_eligible", "ITC eligible")}
      </div>
      {text("payment_terms", "Payment terms", { placeholder: "Net 15", className: "col-span-2 md:col-span-1" })}
      <ReviewField id="f-notes" label="Notes (UTR / reference hints)" issues={headerIssues(issues, "notes")} onResolve={onResolve} isReadOnly={isReadOnly} className="col-span-2 md:col-span-3">
        <textarea
          id="f-notes"
          data-field="notes"
          rows={2}
          className={cn("w-full rounded-md border border-input bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring", lowClass)}
          value={header.notes}
          onChange={(event) => onChange("notes", event.target.value)}
          readOnly={isReadOnly}
        />
      </ReviewField>
    </section>
  );
}
