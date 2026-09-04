import { wordDiff } from "@/lib/diff";
import { cn } from "@/lib/utils";

const OP_CLASS = {
  equal: "",
  insert: "rounded-sm bg-success/15 text-success underline decoration-success/60",
  delete: "rounded-sm bg-danger/15 text-danger line-through",
} as const;

/** AI draft vs sent text at word level. Pure presentation over lib/diff. */
export function WordDiff({ before, after, className }: { before: string; after: string; className?: string }) {
  const segments = wordDiff(before, after);
  return (
    <p className={cn("whitespace-pre-wrap text-sm leading-6", className)} aria-label="Changes between draft and sent text">
      {segments.map((segment, index) => (
        <span key={`${index}-${segment.op}`} data-op={segment.op} className={OP_CLASS[segment.op]}>
          {segment.text}
        </span>
      ))}
    </p>
  );
}
