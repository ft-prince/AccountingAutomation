// Pure form state for the review form: draft vs last-saved snapshot, a local undo stack,
// and the PATCH body. No React, no I/O — the screen wraps this in useReducer.
import type { InvoiceDetail, InvoiceLineWrite, InvoicePatch, SupplyType } from "@/lib/invoices";
import type { HeaderFieldName, LineColumn } from "./issue-map";
import { sameAmount } from "./recompute";

export interface HeaderDraft {
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  place_of_supply_state_code: string;
  supply_type: SupplyType;
  is_reverse_charge: boolean;
  irn: string;
  has_qr: boolean;
  itc_eligible: boolean;
  notes: string;
  payment_terms: string;
}

export type EditableLineColumn = Extract<LineColumn, "description" | "hsn_sac" | "quantity" | "uom" | "unit_price" | "discount" | "rate" | "cess_rate">;

export interface LineDraft {
  key: string;
  id?: string;
  description: string;
  hsn_sac: string;
  quantity: string;
  uom: string;
  unit_price: string;
  discount: string;
  rate: string;
  cess_rate: string;
  confidence?: string;
}

export interface FormSnapshot {
  header: HeaderDraft;
  lines: LineDraft[];
}

export interface FormState {
  invoiceId: string | null;
  draft: FormSnapshot;
  saved: FormSnapshot;
  undo: FormSnapshot[];
  /** Field key of the edit run currently being coalesced into one undo entry. */
  lastEditKey: string | null;
  nextLineKey: number;
}

export type FormAction =
  | { type: "reset"; invoice: InvoiceDetail }
  | { type: "header"; field: HeaderFieldName; value: string | boolean }
  | { type: "line"; index: number; column: EditableLineColumn; value: string }
  | { type: "addLine" }
  | { type: "removeLine"; index: number }
  | { type: "undo" }
  | { type: "saved"; invoice: InvoiceDetail; sentPatch: InvoicePatch };

export const UNDO_LIMIT = 50;
const DEFAULT_QUANTITY = "1";
const ZERO = "0";

const EMPTY_HEADER: HeaderDraft = {
  invoice_number: "",
  invoice_date: "",
  due_date: "",
  place_of_supply_state_code: "",
  supply_type: "intra",
  is_reverse_charge: false,
  irn: "",
  has_qr: false,
  itc_eligible: true,
  notes: "",
  payment_terms: "",
};

export const EMPTY_FORM_STATE: FormState = {
  invoiceId: null,
  draft: { header: EMPTY_HEADER, lines: [] },
  saved: { header: EMPTY_HEADER, lines: [] },
  undo: [],
  lastEditKey: null,
  nextLineKey: 0,
};

export function headerFromInvoice(invoice: InvoiceDetail): HeaderDraft {
  return {
    invoice_number: invoice.invoice_number,
    invoice_date: invoice.invoice_date,
    due_date: invoice.due_date ?? "",
    place_of_supply_state_code: invoice.place_of_supply_state_code ?? "",
    supply_type: invoice.supply_type ?? "intra",
    is_reverse_charge: invoice.is_reverse_charge ?? false,
    irn: invoice.irn ?? "",
    has_qr: invoice.has_qr ?? false,
    itc_eligible: invoice.itc_eligible ?? true,
    notes: invoice.notes ?? "",
    payment_terms: invoice.payment_terms ?? "",
  };
}

export function linesFromInvoice(invoice: InvoiceDetail): LineDraft[] {
  return [...invoice.lines]
    .sort((a, b) => a.line_no - b.line_no)
    .map((line) => ({
      key: line.id,
      id: line.id,
      description: line.description ?? "",
      hsn_sac: line.hsn_sac ?? "",
      quantity: line.quantity ?? DEFAULT_QUANTITY,
      uom: line.uom ?? "",
      unit_price: line.unit_price ?? ZERO,
      discount: line.discount ?? ZERO,
      rate: line.rate ?? ZERO,
      cess_rate: line.cess_rate ?? ZERO,
      confidence: line.confidence,
    }));
}

function snapshotOf(invoice: InvoiceDetail): FormSnapshot {
  return { header: headerFromInvoice(invoice), lines: linesFromInvoice(invoice) };
}

function newLine(key: number): LineDraft {
  return { key: `new-${key}`, description: "", hsn_sac: "", quantity: DEFAULT_QUANTITY, uom: "", unit_price: ZERO, discount: ZERO, rate: ZERO, cess_rate: ZERO };
}

function pushUndo(state: FormState, editKey: string | null): Pick<FormState, "undo" | "lastEditKey"> {
  const isSameRun = editKey !== null && editKey === state.lastEditKey;
  if (isSameRun) return { undo: state.undo, lastEditKey: editKey };
  return { undo: [...state.undo, state.draft].slice(-UNDO_LIMIT), lastEditKey: editKey };
}

export function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case "reset": {
      const snapshot = snapshotOf(action.invoice);
      return { ...EMPTY_FORM_STATE, invoiceId: action.invoice.id, draft: snapshot, saved: snapshot };
    }
    case "saved": {
      // A save that lands after the screen moved on must not clobber the next invoice.
      if (action.invoice.id !== state.invoiceId) return state;
      const snapshot = snapshotOf(action.invoice);
      // Nothing typed since the request left: adopt the server-normalised values and new line ids.
      // Otherwise keep the local draft; only the saved baseline moves.
      const isUnchanged = patchesEqual(toPatch(state.draft), action.sentPatch);
      return { ...state, saved: snapshot, draft: isUnchanged ? snapshot : state.draft };
    }
    case "header": {
      const draft = { ...state.draft, header: { ...state.draft.header, [action.field]: action.value } };
      return { ...state, ...pushUndo(state, `header.${action.field}`), draft };
    }
    case "line": {
      const lines = state.draft.lines.map((line, i) => (i === action.index ? { ...line, [action.column]: action.value } : line));
      return { ...state, ...pushUndo(state, `line.${action.index}.${action.column}`), draft: { ...state.draft, lines } };
    }
    case "addLine": {
      const lines = [...state.draft.lines, newLine(state.nextLineKey)];
      return { ...state, ...pushUndo(state, null), nextLineKey: state.nextLineKey + 1, draft: { ...state.draft, lines } };
    }
    case "removeLine": {
      const lines = state.draft.lines.filter((_, i) => i !== action.index);
      return { ...state, ...pushUndo(state, null), draft: { ...state.draft, lines } };
    }
    case "undo": {
      const previous = state.undo[state.undo.length - 1];
      if (!previous) return state;
      return { ...state, draft: previous, undo: state.undo.slice(0, -1), lastEditKey: null };
    }
  }
}

export function isDirty(state: FormState): boolean {
  return !patchesEqual(toPatch(state.draft), toPatch(state.saved));
}

const DECIMAL_LINE_FIELDS: readonly (keyof InvoiceLineWrite)[] = ["quantity", "unit_price", "discount", "rate", "cess_rate"];
const TEXT_LINE_FIELDS: readonly (keyof InvoiceLineWrite)[] = ["description", "hsn_sac", "uom"];

function linesEqual(a: InvoiceLineWrite, b: InvoiceLineWrite): boolean {
  return TEXT_LINE_FIELDS.every((field) => a[field] === b[field]) && DECIMAL_LINE_FIELDS.every((field) => sameAmount(a[field], b[field]));
}

/** Value-aware equality: "1" and "1.000" are the same quantity, so a server round-trip never re-dirties the form. */
export function patchesEqual(a: InvoicePatch, b: InvoicePatch): boolean {
  const { lines: linesA = [], ...headerA } = a;
  const { lines: linesB = [], ...headerB } = b;
  const headerKeys = new Set([...Object.keys(headerA), ...Object.keys(headerB)] as (keyof typeof headerA)[]);
  for (const key of headerKeys) {
    if ((headerA[key] ?? null) !== (headerB[key] ?? null)) return false;
  }
  return linesA.length === linesB.length && linesA.every((line, i) => linesEqual(line, linesB[i]));
}

export function toPatch(snapshot: FormSnapshot): InvoicePatch {
  const { header, lines } = snapshot;
  return {
    invoice_number: header.invoice_number,
    invoice_date: header.invoice_date,
    due_date: header.due_date || null,
    place_of_supply_state_code: header.place_of_supply_state_code,
    supply_type: header.supply_type,
    is_reverse_charge: header.is_reverse_charge,
    irn: header.irn,
    has_qr: header.has_qr,
    itc_eligible: header.itc_eligible,
    notes: header.notes,
    payment_terms: header.payment_terms,
    lines: lines.map((line) => ({
      description: line.description,
      hsn_sac: line.hsn_sac,
      quantity: line.quantity,
      uom: line.uom,
      unit_price: line.unit_price,
      discount: line.discount,
      rate: line.rate,
      cess_rate: line.cess_rate,
    })),
  };
}
