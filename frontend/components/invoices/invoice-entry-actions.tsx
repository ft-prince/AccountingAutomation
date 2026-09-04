"use client";

import { FileUp, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import { canConfirmInvoices } from "@/lib/roles";
import { InvoiceImportWizard } from "./invoice-import-wizard";
import { NewInvoiceDialog } from "./new-invoice-dialog";

type OpenDialog = "create" | "import" | null;

/** Manual entry and CSV import. Hidden for viewers so the controls are never dead; the
 * API rejects them anyway (owner/accountant only). */
export function InvoiceEntryActions({ role }: { role: string | null | undefined }) {
  const [dialog, setDialog] = useState<OpenDialog>(null);
  if (!canConfirmInvoices(role)) return null;

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setDialog("import")}>
        <FileUp size={16} strokeWidth={ICON_STROKE} aria-hidden /> Import CSV
      </Button>
      <Button size="sm" onClick={() => setDialog("create")}>
        <Plus size={16} strokeWidth={ICON_STROKE} aria-hidden /> New invoice
      </Button>
      <NewInvoiceDialog open={dialog === "create"} onOpenChange={(open) => setDialog(open ? "create" : null)} />
      <InvoiceImportWizard open={dialog === "import"} onOpenChange={(open) => setDialog(open ? "import" : null)} />
    </>
  );
}
