"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useGenerateNarrative } from "@/lib/forecast";
import { toastApiError } from "@/lib/toast";

const LABEL = "Generated summary";

/** §8.8: five plain-English bullets produced from the numbers, never producing numbers; always labelled generated. */
export function NarrativePanel({ runId, narrative, canGenerate }: { runId: string; narrative: string | null; canGenerate: boolean }) {
  const generate = useGenerateNarrative();
  const [text, setText] = useState<string | null>(narrative);
  return (
    <section aria-label={LABEL} className="rounded-card border border-border bg-surface p-5">
      <header className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">{LABEL}</h2>
          <p className="text-xs text-muted">Written by the model from run aggregates only. Treat as commentary, not as figures.</p>
        </div>
        {canGenerate && (
          <Button
            variant="outline"
            size="sm"
            disabled={generate.isPending}
            onClick={() => generate.mutate(runId, { onSuccess: (response) => { setText(response.narrative); if (!response.generated) toast({ title: "No narrative produced", description: "The model returned nothing usable; the numbers above stand on their own." }); }, onError: (error) => toastApiError(error, "Could not generate summary") })}
          >
            <Sparkles strokeWidth={ICON_STROKE} aria-hidden /> {generate.isPending ? "Generating…" : text ? "Regenerate" : "Generate"}
          </Button>
        )}
      </header>
      {text ? <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-6">{text}</pre> : <p className="mt-3 text-sm text-muted">No summary generated for this run.</p>}
    </section>
  );
}
