// Pure state for the manual invoice entry form: the draft, immutable line edits, the
// intra/inter decision (§3.2) and the POST body. No React, no I/O — the dialog wraps this.
import { isDecimalString, type SupplyType } from "@/components/review/recompute";
import type { InvoiceDirection, InvoiceLineWrite } from "@/lib/types";

export interface InvoiceLineDraft {
  /** Stable React key; never sent to the server. */
  key: string;
  description: string;
  hsn_sac: string;
  quantity: string;
  uom: string;
  unit_price: string;
  discount: string;
  rate: string;
  cess_rate: string;
}

export interface InvoiceDraft {
  party: string;
  direction: InvoiceDirection;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  gstin_profile: string;
  place_of_supply_state_code: string;
  is_reverse_charge: boolean;
  irn: string;
  notes: string;
  payment_terms: string;
  lines: InvoiceLineDraft[];
}

/** POST /api/invoices/ body. The create action carries no @extend_schema, so drf-spectacular
 * emits InvoiceList for it and the shape cannot be generated; the line shape is generated. */
export interface NewInvoiceBody {
  party: string;
  direction: InvoiceDirection;
  invoice_number: string;
  invoice_date: string;
  due_date: string | null;
  gstin_profile?: string;
  place_of_supply_state_code?: string;
  is_reverse_charge: boolean;
  irn: string;
  currency: "INR";
  notes: string;
  payment_terms: string;
  lines: InvoiceLineWrite[];
}

const DEFAULT_QUANTITY = "1";
const DEFAULT_RATE = "18";
const ZERO = "0";
const STATE_CODE_PATTERN = /^\d{2}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const NUMERIC_COLUMNS = ["quantity", "unit_price", "discount", "rate", "cess_rate"] as const;

export type NumericLineColumn = (typeof NUMERIC_COLUMNS)[number];
export type LineColumn = keyof Omit<InvoiceLineDraft, "key">;

export function emptyLine(key: string): InvoiceLineDraft {
  return { key, description: "", hsn_sac: "", quantity: DEFAULT_QUANTITY, uom: "nos", unit_price: ZERO, discount: ZERO, rate: DEFAULT_RATE, cess_rate: ZERO };
}

export function emptyDraft(today: string): InvoiceDraft {
  return {
    party: "",
    direction: "inward",
    invoice_number: "",
    invoice_date: today,
    due_date: "",
    gstin_profile: "",
    place_of_supply_state_code: "",
    is_reverse_charge: false,
    irn: "",
    notes: "",
    payment_terms: "",
    lines: [emptyLine("line-0")],
  };
}

export function addLine(draft: InvoiceDraft, key: string): InvoiceDraft {
  return { ...draft, lines: [...draft.lines, emptyLine(key)] };
}

export function removeLine(draft: InvoiceDraft, index: number): InvoiceDraft {
  return { ...draft, lines: draft.lines.filter((_line, i) => i !== index) };
}

export function setLineValue(draft: InvoiceDraft, index: number, column: LineColumn, value: string): InvoiceDraft {
  return { ...draft, lines: draft.lines.map((line, i) => (i === index ? { ...line, [column]: value } : line)) };
}

/** §3.2: supplier state == place of supply → CGST+SGST, otherwise IGST. Unknown states are
 * treated as intra-state, matching the review form's default; the server decides for real. */
export function supplyTypeFor(supplierStateCode: string, placeOfSupplyStateCode: string): SupplyType {
  if (!STATE_CODE_PATTERN.test(supplierStateCode) || !STATE_CODE_PATTERN.test(placeOfSupplyStateCode)) return "intra";
  return supplierStateCode === placeOfSupplyStateCode ? "intra" : "inter";
}

/** Human-readable blockers; an empty array means the form may be submitted. */
export function draftErrors(draft: InvoiceDraft): string[] {
  const errors: string[] = [];
  if (draft.party === "") errors.push("Choose a party.");
  if (draft.invoice_number.trim() === "") errors.push("Invoice number is required.");
  if (!ISO_DATE_PATTERN.test(draft.invoice_date)) errors.push("Invoice date must be a date.");
  if (draft.due_date !== "" && !ISO_DATE_PATTERN.test(draft.due_date)) errors.push("Due date must be a date.");
  if (draft.place_of_supply_state_code !== "" && !STATE_CODE_PATTERN.test(draft.place_of_supply_state_code)) {
    errors.push("Place of supply is a two-digit state code (§3.1).");
  }
  if (draft.lines.length === 0) errors.push("Add at least one line item.");
  draft.lines.forEach((line, index) => {
    const bad = NUMERIC_COLUMNS.filter((column) => !isDecimalString(line[column]));
    if (bad.length > 0) errors.push(`Line ${index + 1}: ${bad.join(", ")} must be a number.`);
  });
  return errors;
}

function toLineWrite(line: InvoiceLineDraft): InvoiceLineWrite {
  return {
    description: line.description,
    hsn_sac: line.hsn_sac,
    quantity: line.quantity,
    uom: line.uom,
    unit_price: line.unit_price,
    discount: line.discount,
    rate: line.rate,
    cess_rate: line.cess_rate,
  };
}

/** Totals are deliberately absent: the server recomputes every tax figure. */
export function toCreateBody(draft: InvoiceDraft): NewInvoiceBody {
  return {
    party: draft.party,
    direction: draft.direction,
    invoice_number: draft.invoice_number.trim(),
    invoice_date: draft.invoice_date,
    due_date: draft.due_date === "" ? null : draft.due_date,
    ...(draft.gstin_profile === "" ? {} : { gstin_profile: draft.gstin_profile }),
    ...(draft.place_of_supply_state_code === "" ? {} : { place_of_supply_state_code: draft.place_of_supply_state_code }),
    is_reverse_charge: draft.is_reverse_charge,
    irn: draft.irn.trim(),
    currency: "INR",
    notes: draft.notes,
    payment_terms: draft.payment_terms,
    lines: draft.lines.map(toLineWrite),
  };
}
