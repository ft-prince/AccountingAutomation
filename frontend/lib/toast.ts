import { toast } from "@/hooks/use-toast";
import { ApiError, type Problem } from "@/lib/api";

/** First human-readable message in an RFC 7807 problem: detail, else the first field error, else title. */
export function problemMessage(problem: Problem): string {
  if (problem.detail) return problem.detail;
  const firstError = Object.values(problem.errors ?? {})[0];
  if (Array.isArray(firstError) && firstError.length > 0) return String(firstError[0]);
  if (typeof firstError === "string") return firstError;
  return problem.title;
}

/** Shows an ApiError (or any thrown value) as a destructive toast. */
export function toastApiError(error: unknown, fallbackTitle = "Something went wrong"): void {
  if (error instanceof ApiError) {
    toast({ variant: "destructive", title: error.problem.title, description: problemMessage(error.problem) });
    return;
  }
  const description = error instanceof Error ? error.message : undefined;
  toast({ variant: "destructive", title: fallbackTitle, description });
}
