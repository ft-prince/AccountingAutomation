// Client-side preview of a bank statement CSV before it is sent to POST /api/bank/statements/import.
// Pure: parses the first rows and guesses which columns hold date / description / amounts / balance
// so the user can confirm the mapping. The server does the authoritative parse.
import { parseCsv } from "@/lib/csv";

export const PREVIEW_ROWS = 6;

export type ColumnRole = "date" | "description" | "debit" | "credit" | "amount" | "balance" | "reference" | "ignore";

export interface ColumnGuess {
  index: number;
  header: string;
  role: ColumnRole;
}

export interface ImportPreview {
  headers: string[];
  rows: string[][];
  columns: ColumnGuess[];
}

const ROLE_PATTERNS: readonly { role: ColumnRole; pattern: RegExp }[] = [
  { role: "date", pattern: /\b(txn|transaction|value)?\s*date\b/i },
  { role: "debit", pattern: /\b(debit|withdrawal|dr)\b/i },
  { role: "credit", pattern: /\b(credit|deposit|cr)\b/i },
  { role: "balance", pattern: /\bbalance\b/i },
  { role: "amount", pattern: /\bamount\b/i },
  { role: "reference", pattern: /\b(ref|reference|chq|cheque|utr)\b/i },
  { role: "description", pattern: /\b(narration|description|particulars|details|remarks)\b/i },
];

export function guessColumnRole(header: string): ColumnRole {
  const match = ROLE_PATTERNS.find((entry) => entry.pattern.test(header.trim()));
  return match ? match.role : "ignore";
}

/** Header row + first `limit` data rows with a guessed role per column. Empty text yields an empty preview. */
export function previewStatement(text: string, limit = PREVIEW_ROWS): ImportPreview {
  const [headers = [], ...rows] = parseCsv(text, limit + 1);
  return {
    headers,
    rows,
    columns: headers.map((header, index) => ({ index, header, role: guessColumnRole(header) })),
  };
}

/** True when the guessed roles could describe a statement: a date plus either an amount or a debit/credit pair. */
export function isMappingUsable(columns: readonly ColumnGuess[]): boolean {
  const roles = new Set(columns.map((column) => column.role));
  return roles.has("date") && (roles.has("amount") || (roles.has("debit") && roles.has("credit")));
}
