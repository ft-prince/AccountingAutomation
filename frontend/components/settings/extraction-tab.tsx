"use client";

import { AlertTriangle } from "lucide-react";
import { QueryState } from "@/components/primitives/query-state";
import { Switch } from "@/components/primitives/switch";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useExtractionSettings, useUpdateExtractionSettings, type ExtractionSettings } from "@/lib/settings";
import { toastApiError } from "@/lib/toast";

interface ToggleSpec {
  key: keyof ExtractionSettings;
  label: string;
  description: string;
}

const TOGGLES: readonly ToggleSpec[] = [
  { key: "extraction_enabled", label: "LLM extraction", description: "Run the extraction pipeline on uploaded documents. Off means uploads wait in the queue." },
  { key: "send_page_images_for_scans", label: "Send page images for scans", description: "For scanned PDFs, send rendered page images to the model instead of text only. Costs more per page." },
  {
    key: "auto_confirm",
    label: "Auto-confirm invoices",
    description: "PROJECT_SPECS §5: default OFF. Only fires when every rules check passes on a known vendor; the model never confirms anything.",
  },
];

/** GET|PUT /api/settings — owner-only PUT; every toggle is disabled for other roles. */
export function ExtractionTab({ isOwner }: { isOwner: boolean }) {
  const settings = useExtractionSettings();
  const update = useUpdateExtractionSettings();

  const toggle = (key: keyof ExtractionSettings, checked: boolean) => {
    if (!settings.data) return;
    update.mutate(
      { ...settings.data, [key]: checked },
      { onSuccess: () => toast({ title: "Settings saved" }), onError: (error) => toastApiError(error, "Could not save settings") },
    );
  };

  return (
    <QueryState isPending={settings.isPending} error={settings.error} onRetry={() => void settings.refetch()}>
      <div className="max-w-xl space-y-4">
        {!isOwner && <p className="text-sm text-muted">Only owners can change extraction settings.</p>}
        {TOGGLES.map((spec) => (
          <div key={spec.key} className="flex items-start justify-between gap-4 rounded-card border border-border bg-surface p-4">
            <div>
              <label htmlFor={`setting-${spec.key}`} className="text-sm font-medium">
                {spec.label}
              </label>
              <p id={`setting-${spec.key}-desc`} className="mt-1 text-xs text-muted">
                {spec.description}
              </p>
              {spec.key === "auto_confirm" && settings.data?.auto_confirm && (
                <p role="status" className="mt-2 inline-flex items-center gap-1 text-xs text-warning">
                  <AlertTriangle size={14} strokeWidth={ICON_STROKE} aria-hidden /> Auto-confirm is ON. Confirmed invoices feed GST returns without a human review.
                </p>
              )}
            </div>
            <Switch
              id={`setting-${spec.key}`}
              aria-describedby={`setting-${spec.key}-desc`}
              checked={settings.data?.[spec.key] ?? false}
              disabled={!isOwner || update.isPending}
              onCheckedChange={(checked) => toggle(spec.key, checked)}
            />
          </div>
        ))}
      </div>
    </QueryState>
  );
}
