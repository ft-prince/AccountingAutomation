import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** Native checkbox tinted with the accent; keyboard and screen-reader semantics come for free. */
export const Checkbox = forwardRef<HTMLInputElement, Omit<InputHTMLAttributes<HTMLInputElement>, "type">>(function Checkbox({ className, ...props }, ref) {
  return <input ref={ref} type="checkbox" className={cn("h-4 w-4 cursor-pointer rounded-sm border-border accent-accent", className)} {...props} />;
});
