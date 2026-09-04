import type { Metadata } from "next";
import { ReconciliationView } from "@/components/reconciliation/reconciliation-view";

export const metadata: Metadata = { title: "Reconciliation · Nexren Finance" };

export default function ReconciliationPage() {
  return <ReconciliationView />;
}
