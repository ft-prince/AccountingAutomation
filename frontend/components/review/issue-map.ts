// Maps ValidationIssue.field names onto form locations so issues render inline under their field.
// Unknown fields fall through to the general list at the top of the form.

export type HeaderFieldName =
  | "invoice_number"
  | "invoice_date"
  | "due_date"
  | "place_of_supply_state_code"
  | "supply_type"
  | "is_reverse_charge"
  | "irn"
  | "has_qr"
  | "itc_eligible"
  | "notes"
  | "payment_terms";

export type LineColumn = "description" | "hsn_sac" | "quantity" | "uom" | "unit_price" | "discount" | "rate" | "cess_rate" | "taxable_value" | "cgst" | "sgst" | "igst" | "cess" | "line_total";

export type IssueLocation =
  | { kind: "header"; field: HeaderFieldName }
  | { kind: "line"; index: number; column: LineColumn }
  | { kind: "party" }
  | { kind: "totals" }
  | { kind: "general" };

const HEADER_FIELDS = new Set<string>([
  "invoice_number",
  "invoice_date",
  "due_date",
  "place_of_supply_state_code",
  "supply_type",
  "is_reverse_charge",
  "irn",
  "has_qr",
  "itc_eligible",
  "notes",
  "payment_terms",
]);

const HEADER_ALIASES: Record<string, HeaderFieldName> = {
  place_of_supply: "place_of_supply_state_code",
  pos: "place_of_supply_state_code",
  reverse_charge: "is_reverse_charge",
  qr: "has_qr",
  date: "invoice_date",
  number: "invoice_number",
};

const PARTY_FIELDS = new Set(["party", "supplier_gstin", "recipient_gstin", "supplier_name", "recipient_name", "supplier_address", "recipient_address", "supplier_state_code", "recipient_state_code", "gstin"]);

const TOTALS_FIELDS = new Set(["stated_total", "total", "taxable_value", "cgst", "sgst", "igst", "cess", "round_off", "arithmetic", "grand_total"]);

const LINE_COLUMNS = new Set<string>(["description", "hsn_sac", "quantity", "uom", "unit_price", "discount", "rate", "cess_rate", "taxable_value", "cgst", "sgst", "igst", "cess", "line_total"]);

// "lines[0].cgst", "lines.0.cgst", "lines[0]" all resolve to line 0.
const LINE_RE = /^lines?[[.](\d+)\]?(?:[.[]?([a-z_]+)\]?)?$/;

export function locateIssue(field: string | undefined | null): IssueLocation {
  const name = (field ?? "").trim();
  if (!name) return { kind: "general" };

  const lineMatch = LINE_RE.exec(name);
  if (lineMatch) {
    const index = Number(lineMatch[1]);
    const column = lineMatch[2] && LINE_COLUMNS.has(lineMatch[2]) ? (lineMatch[2] as LineColumn) : "description";
    return { kind: "line", index, column };
  }
  if (HEADER_FIELDS.has(name)) return { kind: "header", field: name as HeaderFieldName };
  if (name in HEADER_ALIASES) return { kind: "header", field: HEADER_ALIASES[name] };
  if (PARTY_FIELDS.has(name)) return { kind: "party" };
  if (TOTALS_FIELDS.has(name)) return { kind: "totals" };
  return { kind: "general" };
}

export interface IssueLike {
  id: string;
  field?: string;
  severity: string;
  resolved_at?: string | null;
}

export function isUnresolvedError(issue: IssueLike): boolean {
  return issue.severity === "error" && !issue.resolved_at;
}

export function issuesAt<T extends IssueLike>(issues: readonly T[], predicate: (location: IssueLocation) => boolean): T[] {
  return issues.filter((issue) => predicate(locateIssue(issue.field)));
}

export function headerIssues<T extends IssueLike>(issues: readonly T[], field: HeaderFieldName): T[] {
  return issuesAt(issues, (loc) => loc.kind === "header" && loc.field === field);
}

export function lineIssues<T extends IssueLike>(issues: readonly T[], index: number): T[] {
  return issuesAt(issues, (loc) => loc.kind === "line" && loc.index === index);
}
