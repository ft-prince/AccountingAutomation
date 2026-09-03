import Link from "next/link";
import { DEFAULT_BRAND_NAME, ROUTES } from "@/lib/routes";
import { cn } from "@/lib/utils";

interface BrandMarkProps {
  name?: string | null;
  compact?: boolean;
  className?: string;
}

/** §9: the logo mark is the brand name with a warm-orange terminal dot. */
export function BrandMark({ name, compact = false, className }: BrandMarkProps) {
  const label = name?.trim() || DEFAULT_BRAND_NAME;
  return (
    <Link href={ROUTES.dashboard} className={cn("font-display text-xl italic leading-none tracking-tight", className)} aria-label={label}>
      {compact ? label.charAt(0) : label}
      <span className="text-accent" aria-hidden>
        .
      </span>
    </Link>
  );
}
