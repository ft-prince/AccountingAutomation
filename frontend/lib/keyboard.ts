// /review keyboard map (PROJECT_SPECS §11: keyboard-first). Pure and testable:
// `resolveShortcut(eventLike)` returns an action or null; the screen decides what to do.

export type ShortcutAction = "confirm" | "reject" | "duplicate" | "undo" | "help" | "escape" | "next" | "previous";

export interface KeyTargetLike {
  tagName?: string;
  isContentEditable?: boolean;
}

export interface KeyEventLike {
  key: string;
  metaKey?: boolean;
  ctrlKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
  target?: KeyTargetLike | EventTarget | null;
}

export interface ShortcutBinding {
  keys: string;
  action: ShortcutAction;
  description: string;
}

/** Shown in the "?" overlay; the source of truth for what the resolver does. */
export const SHORTCUT_BINDINGS: readonly ShortcutBinding[] = [
  { keys: "Enter", action: "confirm", description: "Confirm and advance (⌘/Ctrl+Enter from anywhere)" },
  { keys: "R", action: "reject", description: "Reject with a reason" },
  { keys: "D", action: "duplicate", description: "Mark as duplicate" },
  { keys: "⌘/Ctrl+Z", action: "undo", description: "Undo the last field edit" },
  { keys: "J", action: "next", description: "Next invoice in the queue" },
  { keys: "K", action: "previous", description: "Previous invoice in the queue" },
  { keys: "?", action: "help", description: "Show this overlay" },
  { keys: "Esc", action: "escape", description: "Close overlays" },
];

const TEXT_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);
const ACTIVATION_TAGS = new Set(["BUTTON", "A", "SUMMARY"]);

function targetTag(target: KeyEventLike["target"]): string {
  const tagName = (target as KeyTargetLike | null | undefined)?.tagName;
  return typeof tagName === "string" ? tagName.toUpperCase() : "";
}

export function isTypingTarget(target: KeyEventLike["target"]): boolean {
  if (!target) return false;
  if ((target as KeyTargetLike).isContentEditable === true) return true;
  return TEXT_TAGS.has(targetTag(target));
}

function isModified(event: KeyEventLike): boolean {
  return Boolean(event.metaKey || event.ctrlKey);
}

const PLAIN_KEY_ACTIONS: Record<string, ShortcutAction> = {
  r: "reject",
  d: "duplicate",
  j: "next",
  k: "previous",
  "?": "help",
};

/**
 * Maps a keydown to a review action.
 * - Esc and ⌘/Ctrl combos work everywhere.
 * - Enter confirms from an input; inside a textarea it inserts a newline.
 * - Single-letter shortcuts are ignored while typing so "r" in a field never rejects.
 */
export function resolveShortcut(event: KeyEventLike): ShortcutAction | null {
  if (event.altKey) return null;
  if (event.key === "Escape") return "escape";

  if (isModified(event)) {
    if (event.key === "Enter") return "confirm";
    if (event.key.toLowerCase() === "z" && !event.shiftKey) return "undo";
    return null;
  }

  const tag = targetTag(event.target);
  if (event.key === "Enter") {
    if (tag === "TEXTAREA" || ACTIVATION_TAGS.has(tag)) return null;
    return "confirm";
  }
  if (isTypingTarget(event.target)) return null;
  return PLAIN_KEY_ACTIONS[event.key.toLowerCase()] ?? (event.key === "?" ? "help" : null);
}
