"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import { cursorFromUrl } from "@/lib/query";

export interface CursorPagerProps {
  next: string | null | undefined;
  previous: string | null | undefined;
  onCursor: (cursor: string | null) => void;
  isFetching?: boolean;
  /** Rows on the current page, shown as "25 rows". */
  count?: number;
}

/** DRF cursor pagination: only next/previous are knowable, so no page numbers are shown. */
export function CursorPager({ next, previous, onCursor, isFetching = false, count }: CursorPagerProps) {
  const nextCursor = cursorFromUrl(next ?? null);
  const hasPrevious = Boolean(previous);
  const previousCursor = cursorFromUrl(previous ?? null);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 text-sm text-muted">
      <span className="tabular-nums">{count !== undefined ? `${count} rows` : ""}</span>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={!hasPrevious || isFetching} onClick={() => onCursor(previousCursor)}>
          <ChevronLeft strokeWidth={ICON_STROKE} aria-hidden /> Previous
        </Button>
        <Button variant="outline" size="sm" disabled={!nextCursor || isFetching} onClick={() => onCursor(nextCursor)}>
          Next <ChevronRight strokeWidth={ICON_STROKE} aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
