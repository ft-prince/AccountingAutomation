"use client";

import { AlertTriangle, Check, OctagonAlert } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ICON_STROKE } from "@/lib/constants";
import type { ValidationIssue } from "@/lib/invoices";
import { cn } from "@/lib/utils";

export interface IssueListProps {
  issues: readonly ValidationIssue[];
  onResolve: (issueId: string, note: string) => void;
  resolvingId?: string | null;
  isReadOnly?: boolean;
  className?: string;
}

const SEVERITY_STYLE: Record<string, { text: string; Icon: typeof AlertTriangle }> = {
  error: { text: "text-danger", Icon: OctagonAlert },
  warning: { text: "text-warning", Icon: AlertTriangle },
};

/** Validation issues rendered next to the field they belong to, each with an inline Resolve. */
export function IssueList({ issues, onResolve, resolvingId = null, isReadOnly = false, className }: IssueListProps) {
  if (issues.length === 0) return null;
  return (
    <ul className={cn("space-y-1", className)}>
      {issues.map((issue) => (
        <IssueRow key={issue.id} issue={issue} onResolve={onResolve} isResolving={resolvingId === issue.id} isReadOnly={isReadOnly} />
      ))}
    </ul>
  );
}

interface IssueRowProps {
  issue: ValidationIssue;
  onResolve: (issueId: string, note: string) => void;
  isResolving: boolean;
  isReadOnly: boolean;
}

function IssueRow({ issue, onResolve, isResolving, isReadOnly }: IssueRowProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [note, setNote] = useState("");
  const isResolved = Boolean(issue.resolved_at);
  const style = SEVERITY_STYLE[issue.severity] ?? SEVERITY_STYLE.warning;

  if (isResolved) {
    return (
      <li className="flex items-start gap-1.5 text-xs text-muted">
        <Check size={14} strokeWidth={ICON_STROKE} className="mt-0.5 shrink-0 text-success" aria-hidden />
        <span>
          <span className="line-through">{issue.message}</span>
          {issue.note ? ` — ${issue.note}` : ""}
        </span>
      </li>
    );
  }

  const submit = () => {
    onResolve(issue.id, note.trim());
    setIsEditing(false);
  };

  return (
    <li data-severity={issue.severity} className={cn("flex flex-col gap-1 text-xs", style.text)}>
      <div className="flex items-start gap-1.5">
        <style.Icon size={14} strokeWidth={ICON_STROKE} className="mt-0.5 shrink-0" aria-hidden />
        <span className="flex-1">
          <span className="font-medium">{issue.code}</span> · {issue.message}
        </span>
        {!isReadOnly && !isEditing && (
          <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => setIsEditing(true)} disabled={isResolving}>
            {isResolving ? "Resolving…" : "Resolve"}
          </Button>
        )}
      </div>
      {isEditing && (
        <form
          className="flex items-center gap-1 pl-5"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <Input
            aria-label={`Resolution note for ${issue.code}`}
            className="h-7 text-xs"
            placeholder="Why is this fine? (optional)"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.stopPropagation();
                setIsEditing(false);
              }
            }}
          />
          <Button type="submit" size="sm" className="h-7 text-xs">
            Mark resolved
          </Button>
          <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setIsEditing(false)}>
            Cancel
          </Button>
        </form>
      )}
    </li>
  );
}
