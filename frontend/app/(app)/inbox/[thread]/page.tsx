import type { Metadata } from "next";
import { ThreadView } from "@/components/inbox/thread-view";

export const metadata: Metadata = { title: "Thread · Nexren Finance" };

export default async function ThreadPage({ params }: { params: Promise<{ thread: string }> }) {
  const { thread } = await params;
  return <ThreadView id={thread} />;
}
