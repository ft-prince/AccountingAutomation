import type { Metadata } from "next";
import { GuideView } from "@/components/guide/guide-view";

export const metadata: Metadata = { title: "Guide · Nexren Finance" };

export default function GuidePage() {
  return <GuideView />;
}
