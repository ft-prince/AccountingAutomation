import type { Metadata } from "next";
import { PartiesView } from "@/components/parties/parties-view";

export const metadata: Metadata = { title: "Parties · Nexren Finance" };

export default function PartiesPage() {
  return <PartiesView />;
}
