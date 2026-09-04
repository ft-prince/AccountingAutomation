import type { Metadata } from "next";
import { ReviewScreen } from "@/components/review/review-screen";

export const metadata: Metadata = { title: "Review · Nexren Finance" };

// Rendered per request: app/(app)/[section] prerenders a "/review" placeholder via
// generateStaticParams, and two static outputs for the same path collide at build time.
// Dynamic rendering keeps this route matched first (static segment beats [section]).
export const dynamic = "force-dynamic";

export default function ReviewPage() {
  return <ReviewScreen />;
}
