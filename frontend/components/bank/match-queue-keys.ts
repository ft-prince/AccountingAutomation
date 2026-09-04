// Pure key → action mapping for the bank match queue (§11 /bank three-column queue).
export type MatchQueueAction = "next" | "previous" | "accept" | "ignore" | { candidate: number };

export interface KeyLike {
  key: string;
  metaKey?: boolean;
  ctrlKey?: boolean;
  altKey?: boolean;
  target?: { tagName?: string; isContentEditable?: boolean } | null;
}

const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);
const MAX_CANDIDATE_KEY = 9;

export function resolveMatchQueueKey(event: KeyLike): MatchQueueAction | null {
  if (event.metaKey || event.ctrlKey || event.altKey) return null;
  const tag = event.target?.tagName ?? "";
  if (TYPING_TAGS.has(tag) || event.target?.isContentEditable) return null;
  switch (event.key) {
    case "j":
    case "J":
    case "ArrowDown":
      return "next";
    case "k":
    case "K":
    case "ArrowUp":
      return "previous";
    case "Enter":
    case "a":
    case "A":
      return "accept";
    case "i":
    case "I":
      return "ignore";
    default: {
      const digit = Number(event.key);
      return Number.isInteger(digit) && digit >= 1 && digit <= MAX_CANDIDATE_KEY ? { candidate: digit - 1 } : null;
    }
  }
}
