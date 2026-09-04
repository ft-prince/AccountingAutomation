"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useReducer } from "react";
import { type InvoiceList, invoiceKeys, prefetchInvoice, useReviewQueue } from "@/lib/invoices";
import { currentId, EMPTY_QUEUE, type QueueAction, queueReducer, remainingCount } from "./queue-state";

/** Fetch the next page once this many invoices remain ahead of the cursor. */
const PAGE_AHEAD_MARGIN = 3;

export interface ReviewQueueApi {
  currentId: string | null;
  nextId: string | null;
  position: number;
  total: number;
  remaining: number;
  isPending: boolean;
  error: Error | null;
  refetch: () => void;
  dispatch: (action: QueueAction) => void;
  summaryOf: (id: string) => InvoiceList | undefined;
}

/** The server queue (confidence asc) folded into a local cursor with optimistic done-marks. */
export function useReviewQueueState(): ReviewQueueApi {
  const client = useQueryClient();
  const query = useReviewQueue();
  const [state, dispatch] = useReducer(queueReducer, EMPTY_QUEUE);

  const summaries = useMemo(() => query.data?.pages.flatMap((page) => page.results) ?? [], [query.data]);
  const ids = useMemo(() => summaries.map((invoice) => invoice.id), [summaries]);

  useEffect(() => {
    dispatch({ type: "ids", ids });
  }, [ids]);

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query;
  useEffect(() => {
    const ahead = state.ids.length - state.index;
    if (hasNextPage && !isFetchingNextPage && ahead <= PAGE_AHEAD_MARGIN) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, state.ids.length, state.index]);

  const current = currentId(state);
  const nextId = state.ids.slice(state.index + 1).find((id) => !state.done.includes(id)) ?? null;

  useEffect(() => {
    if (nextId) void prefetchInvoice(client, nextId);
  }, [client, nextId]);

  // The queue is cached for the whole visit; a fresh visit starts from the server's order.
  useEffect(() => {
    return () => {
      void client.invalidateQueries({ queryKey: invoiceKeys.queue() });
    };
  }, [client]);

  return {
    currentId: current,
    nextId,
    position: Math.min(state.index + 1, state.ids.length),
    total: state.ids.length,
    remaining: remainingCount(state),
    isPending: query.isPending,
    error: query.error,
    refetch: () => void query.refetch(),
    dispatch,
    summaryOf: (id) => summaries.find((invoice) => invoice.id === id),
  };
}
