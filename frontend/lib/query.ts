// Query-string and cursor-pagination helpers shared by every list hook.

export type QueryValue = string | number | boolean | null | undefined;

export interface Paginated<T> {
  results: T[];
  next: string | null;
  previous: string | null;
}

/** Serialises only present, non-empty values: {a: "1", b: ""} → "?a=1". Keys are emitted in insertion order. */
export function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

/** Extracts the `cursor` param from a DRF next/previous URL. */
export function cursorFromUrl(url: string | null): string | null {
  if (!url) return null;
  try {
    return new URL(url, "http://localhost").searchParams.get("cursor");
  } catch {
    return null;
  }
}
