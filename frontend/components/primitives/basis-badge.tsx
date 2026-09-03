import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type ReportBasis = "accrual" | "cash";

export interface BasisBadgeProps {
  basis: ReportBasis;
  /** needs_review invoices excluded from the figures (§7.1: a number without its denominator is a lie). */
  pendingCount: number;
  className?: string;
}

const BASIS_LABEL: Record<ReportBasis, string> = { accrual: "Accrual", cash: "Cash" };

export function BasisBadge({ basis, pendingCount, className }: BasisBadgeProps) {
  return (
    <Badge variant="outline" className={cn("font-medium text-muted tabular-nums", className)}>
      {BASIS_LABEL[basis]} · {pendingCount} pending
    </Badge>
  );
}
