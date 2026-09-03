import { LayoutDashboard } from "lucide-react";
import type { Metadata } from "next";
import { EmptyState } from "@/components/primitives/empty-state";

export const metadata: Metadata = { title: "Dashboard · Nexren Finance" };

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">
        Cashflow, <span className="font-display italic text-accent">forecast</span>.
      </h1>
      <EmptyState
        icon={LayoutDashboard}
        title="Dashboard arrives with Phase 11"
        description="KPI tiles, the 13-week forecast band and P&L charts land here once the reporting endpoints are wired up (PROJECT_SPECS §7.4)."
      />
    </div>
  );
}
