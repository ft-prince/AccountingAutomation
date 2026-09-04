"use client";

import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { problemMessage } from "@/lib/toast";

export interface QueryStateProps {
  isPending: boolean;
  error: unknown;
  onRetry?: () => void;
  /** Skeleton height while loading. */
  skeletonClassName?: string;
  children: ReactNode;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return problemMessage(error.problem);
  return error instanceof Error ? error.message : "Request failed";
}

/** Loading skeleton → error card with retry → children. Errors are values shown to the user, never swallowed. */
export function QueryState({ isPending, error, onRetry, skeletonClassName = "h-40 w-full", children }: QueryStateProps) {
  if (isPending) return <Skeleton className={skeletonClassName} aria-busy />;
  if (error) {
    return (
      <div role="alert" className="flex flex-col items-start gap-2 rounded-card border border-danger bg-surface p-4 text-sm">
        <p className="font-medium text-danger">Could not load</p>
        <p className="text-muted">{errorMessage(error)}</p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
    );
  }
  return <>{children}</>;
}
