import type { Metadata } from "next";
import { UploadView } from "@/components/upload/upload-view";

export const metadata: Metadata = { title: "Upload · Nexren Finance" };

export default function UploadPage() {
  return <UploadView />;
}
