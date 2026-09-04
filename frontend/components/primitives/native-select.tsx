import { forwardRef, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const NATIVE_SELECT_CLASS =
  "h-9 rounded-full border border-input bg-surface px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50";

/** Native <select> styled like the period picker; used for filters and short enum choices. */
export const NativeSelect = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function NativeSelect(
  { className, ...props },
  ref,
) {
  return <select ref={ref} className={cn(NATIVE_SELECT_CLASS, className)} {...props} />;
});
