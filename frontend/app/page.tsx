import { redirect } from "next/navigation";
import { ROUTES } from "@/lib/routes";

// middleware.ts already routes "/" by session; this covers direct renders.
export default function Home() {
  redirect(ROUTES.dashboard);
}
