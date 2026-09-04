// Word-level diff (longest common subsequence). Pure; used to show what the reviewer changed
// between the AI draft and the text that was actually sent (§6.7 edit distance, made visible).

export type DiffOp = "equal" | "insert" | "delete";
export interface DiffSegment {
  op: DiffOp;
  text: string;
}

/** Splits on whitespace but keeps the whitespace tokens so the rendered diff preserves layout. */
export function tokenize(text: string): string[] {
  return text.split(/(\s+)/).filter((token) => token.length > 0);
}

function lcsTable(a: readonly string[], b: readonly string[]): number[][] {
  const table: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  return table;
}

function pushSegment(segments: DiffSegment[], op: DiffOp, text: string): DiffSegment[] {
  const last = segments[segments.length - 1];
  if (last && last.op === op) return [...segments.slice(0, -1), { op, text: last.text + text }];
  return [...segments, { op, text }];
}

/** `wordDiff(before, after)` → segments in reading order; adjacent same-op tokens are merged. */
export function wordDiff(before: string, after: string): DiffSegment[] {
  const a = tokenize(before);
  const b = tokenize(after);
  const table = lcsTable(a, b);
  let segments: DiffSegment[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      segments = pushSegment(segments, "equal", a[i]);
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      segments = pushSegment(segments, "delete", a[i]);
      i += 1;
    } else {
      segments = pushSegment(segments, "insert", b[j]);
      j += 1;
    }
  }
  for (; i < a.length; i += 1) segments = pushSegment(segments, "delete", a[i]);
  for (; j < b.length; j += 1) segments = pushSegment(segments, "insert", b[j]);
  return segments;
}

export function hasChanges(segments: readonly DiffSegment[]): boolean {
  return segments.some((segment) => segment.op !== "equal");
}
