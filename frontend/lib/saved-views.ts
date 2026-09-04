// Saved invoice views: per-user, browser-local (localStorage), keyed by the user id so two accounts
// on one machine never see each other's views.
import type { InvoiceFilters } from "@/lib/invoice-filters";

export interface SavedView {
  name: string;
  params: InvoiceFilters;
  createdAt: string;
}

const STORAGE_PREFIX = "nexren:invoice-views:";

function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}${userId}`;
}

function readStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function loadSavedViews(userId: string): SavedView[] {
  const storage = readStorage();
  if (!storage) return [];
  try {
    const parsed: unknown = JSON.parse(storage.getItem(storageKey(userId)) ?? "[]");
    return Array.isArray(parsed) ? (parsed as SavedView[]) : [];
  } catch {
    return [];
  }
}

function writeSavedViews(userId: string, views: readonly SavedView[]): void {
  readStorage()?.setItem(storageKey(userId), JSON.stringify(views));
}

/** Adds or replaces a view by name; returns the new list. */
export function saveView(userId: string, view: Omit<SavedView, "createdAt">): SavedView[] {
  const next = [...loadSavedViews(userId).filter((existing) => existing.name !== view.name), { ...view, createdAt: new Date().toISOString() }];
  writeSavedViews(userId, next);
  return next;
}

export function deleteView(userId: string, name: string): SavedView[] {
  const next = loadSavedViews(userId).filter((existing) => existing.name !== name);
  writeSavedViews(userId, next);
  return next;
}
