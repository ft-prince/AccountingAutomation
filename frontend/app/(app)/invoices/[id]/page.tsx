import type { Metadata } from "next";
import { InvoiceDetailView } from "@/components/invoices/invoice-detail-view";

export const metadata: Metadata = { title: "Invoice · Nexren Finance" };

export default async function InvoiceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <InvoiceDetailView id={id} />;
}
