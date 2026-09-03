import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { ICON_STROKE } from "@/lib/constants";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center rounded-card border border-dashed border-border px-6 py-12 text-center", className)}>
      <Icon size={28} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden />
      <h3 className="mt-4 font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
