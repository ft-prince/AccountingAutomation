"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { NativeSelect } from "@/components/primitives/native-select";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { Tabs } from "@/components/primitives/tabs";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import { isUnallocated, usePayments } from "@/lib/payments";
import type { Payment, PaymentDirection } from "@/lib/types";
import { AllocateDialog } from "./allocate-dialog";
import { PaymentsTable } from "./payments-table";
import { RecordPaymentDialog } from "./record-payment-dialog";

type View = "unallocated" | "all";
const TABS = [
  { value: "unallocated", label: "Unallocated" },
  { value: "all", label: "All payments" },
] as const;

export function PaymentsView() {
  const [view, setView] = useState<View>("unallocated");
  const [direction, setDirection] = useState<PaymentDirection | "">("");
  const [isRecording, setIsRecording] = useState(false);
  const [allocating, setAllocating] = useState<Payment | null>(null);
  const payments = usePayments({ direction });

  // The server's ?unallocated=1 filter is not usable yet (500); computed client-side from amount − allocated.
  const rows = (payments.data?.results ?? []).filter((payment) => view === "all" || isUnallocated(payment));

  return (
    <div className="space-y-5">
      <PageHeader
        title="Record &"
        emphasis="allocate"
        description="Payments settle confirmed invoices; the remainder can never go negative."
        actions={
          <Button onClick={() => setIsRecording(true)}>
            <Plus strokeWidth={ICON_STROKE} aria-hidden /> Record payment
          </Button>
        }
      />
      <div className="flex flex-wrap items-center gap-3">
        <Tabs items={TABS} value={view} onChange={setView} ariaLabel="Payment views" />
        <NativeSelect aria-label="Direction" value={direction} onChange={(event) => setDirection(event.target.value as PaymentDirection | "")}>
          <option value="">Received & made</option>
          <option value="received">Received</option>
          <option value="made">Made</option>
        </NativeSelect>
        {payments.data && <span className="text-sm text-muted tabular-nums">{rows.length} shown</span>}
      </div>
      <QueryState isPending={payments.isPending} error={payments.error} onRetry={() => payments.refetch()} skeletonClassName="h-80 w-full">
        <div className="rounded-card border border-border bg-surface">
          <PaymentsTable payments={rows} onAllocate={setAllocating} />
        </div>
      </QueryState>
      <RecordPaymentDialog open={isRecording} onOpenChange={setIsRecording} />
      <AllocateDialog payment={allocating} onOpenChange={(open) => !open && setAllocating(null)} />
    </div>
  );
}
