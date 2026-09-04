import type { Metadata } from "next";
import { Suspense } from "react";
import { InvoicesView } from "@/components/invoices/invoices-view";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Invoices · Nexren Finance" };

export default function InvoicesPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <InvoicesView />
    </Suspense>
  );
}
