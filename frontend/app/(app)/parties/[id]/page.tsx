import type { Metadata } from "next";
import { PartyDetailView } from "@/components/parties/party-detail-view";

export const metadata: Metadata = { title: "Party · Nexren Finance" };

export default async function PartyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PartyDetailView id={id} />;
}
