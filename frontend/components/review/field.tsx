"use client";

import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";
import type { ValidationIssue } from "@/lib/invoices";
import { cn } from "@/lib/utils";
import { IssueList } from "./issue-list";

/** Accent border marks a field the extractor was unsure about (PROJECT_SPECS §5, < 0.90). */
export function confidenceClass(isLow: boolean): string {
  return isLow ? "border-accent focus-visible:ring-accent" : "";
}

export interface ReviewFieldProps {
  id: string;
  label: string;
  children: ReactNode;
  issues?: readonly ValidationIssue[];
  onResolve?: (issueId: string, note: string) => void;
  isReadOnly?: boolean;
  className?: string;
}

/** Label + control + the validation issues that point at this field. */
export function ReviewField({ id, label, children, issues = [], onResolve, isReadOnly = false, className }: ReviewFieldProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <Label htmlFor={id} className="text-xs text-muted">
        {label}
      </Label>
      {children}
      {onResolve && <IssueList issues={issues} onResolve={onResolve} isReadOnly={isReadOnly} />}
    </div>
  );
}
