// Confidence gating for the review form (PROJECT_SPECS §5: fields under 0.90 need a human eye).
// The API exposes invoice-level and line-level confidence only; header fields inherit the
// invoice figure, line cells inherit their line's figure.
import Big from "big.js";
import type { HeaderFieldName } from "./issue-map";

export const LOW_CONFIDENCE_THRESHOLD = "0.90";

const DECIMAL_RE = /^\d+(\.\d+)?$/;

export function isLowConfidence(confidence: string | null | undefined): boolean {
  if (!confidence || !DECIMAL_RE.test(confidence.trim())) return false;
  return new Big(confidence.trim()).lt(LOW_CONFIDENCE_THRESHOLD);
}

/** Tab order of the header form; the first low-confidence entry receives focus. */
export const HEADER_FIELD_ORDER: readonly HeaderFieldName[] = [
  "invoice_number",
  "invoice_date",
  "due_date",
  "supply_type",
  "place_of_supply_state_code",
  "is_reverse_charge",
  "irn",
  "has_qr",
  "itc_eligible",
  "payment_terms",
  "notes",
];

export type FocusTarget = { kind: "header"; field: HeaderFieldName } | { kind: "line"; index: number };

export function fieldSelector(target: FocusTarget): string {
  return target.kind === "header" ? `[data-field="${target.field}"]` : `[data-field="lines.${target.index}.description"]`;
}

/** First field that needs attention: a low-confidence header field, else the first low-confidence line, else the first field. */
export function firstFocusTarget(invoiceConfidence: string | undefined, lineConfidences: readonly (string | undefined)[]): FocusTarget {
  if (isLowConfidence(invoiceConfidence)) return { kind: "header", field: HEADER_FIELD_ORDER[0] };
  const lowLine = lineConfidences.findIndex((confidence) => isLowConfidence(confidence));
  if (lowLine >= 0) return { kind: "line", index: lowLine };
  return { kind: "header", field: HEADER_FIELD_ORDER[0] };
}
