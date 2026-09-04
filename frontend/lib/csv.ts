// Minimal RFC 4180 CSV parse/serialise. Used for the bank-import mapping preview (first rows only)
// and for client-side exports of already-loaded rows. No dependency on Papa Parse (CLAUDE.md §4).

/** Parses CSV text into rows of fields, honouring double-quoted fields with embedded commas, quotes and newlines. */
export function parseCsv(text: string, limit = Number.POSITIVE_INFINITY): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let isQuoted = false;
  let index = 0;

  const pushField = () => {
    row = [...row, field];
    field = "";
  };
  const pushRow = () => {
    if (row.length > 0 || field.length > 0) {
      pushField();
      rows.push(row);
    }
    row = [];
  };

  while (index < text.length && rows.length < limit) {
    const char = text[index];
    if (isQuoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 2;
        continue;
      }
      if (char === '"') {
        isQuoted = false;
        index += 1;
        continue;
      }
      field += char;
      index += 1;
      continue;
    }
    if (char === '"') {
      isQuoted = true;
    } else if (char === ",") {
      pushField();
    } else if (char === "\r") {
      // swallow; the following \n ends the row
    } else if (char === "\n") {
      pushRow();
    } else {
      field += char;
    }
    index += 1;
  }
  if (rows.length < limit && (row.length > 0 || field.length > 0)) pushRow();
  return rows;
}

function escapeCell(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Serialises a header row plus data rows. Every cell is stringified as-is (money stays a decimal string). */
export function toCsv(headers: readonly string[], rows: readonly (readonly (string | number | null | undefined)[])[]): string {
  const lines = [headers, ...rows].map((cells) => cells.map((cell) => escapeCell(cell === null || cell === undefined ? "" : String(cell))).join(","));
  return lines.join("\r\n");
}

/** Triggers a browser download of CSV text. No-op outside the browser. */
export function downloadCsv(filename: string, csv: string): void {
  if (typeof document === "undefined") return;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
