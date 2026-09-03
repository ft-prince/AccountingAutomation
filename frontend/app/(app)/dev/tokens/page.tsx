import { FileText, Inbox } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";
import { BasisBadge } from "@/components/primitives/basis-badge";
import { EmptyState } from "@/components/primitives/empty-state";
import { MoneyText } from "@/components/primitives/money-text";
import { StatTile } from "@/components/primitives/stat-tile";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { DARK_TOKENS, LIGHT_TOKENS } from "@/lib/tokens";
import { PeriodPickerDemo } from "./period-picker-demo";
import { ErrorBoundaryDemo } from "./error-boundary-demo";
import { ThemeFromQuery } from "./theme-from-query";

export const metadata: Metadata = { title: "Design tokens · Nexren Finance" };

const SANS_WEIGHTS = [400, 500, 600, 700, 800] as const;
const SAMPLE_MONEY = ["123456.78", "12500000", "-1234.5", "0.1"] as const;

function Swatches({ title, tokens }: { title: string; tokens: Record<string, string> }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(tokens).map(([name, hex]) => (
          <div key={name} className="rounded-card border border-border bg-surface p-3">
            <div className="h-12 rounded-md border border-border" style={{ backgroundColor: hex }} />
            <p className="mt-2 text-sm font-medium">{name}</p>
            <p className="font-mono text-xs uppercase text-muted">{hex}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function TokensPage() {
  return (
    <div className="space-y-10 pb-16">
      <Suspense fallback={null}>
        <ThemeFromQuery />
      </Suspense>
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Design <span className="font-display italic text-accent">tokens</span>.
          </h1>
          <p className="mt-1 text-sm text-muted">PROJECT_SPECS §9 — every colour, both fonts, every primitive. Verify in light and dark.</p>
        </div>
        <ThemeToggle />
      </header>

      <Swatches title="Light palette" tokens={LIGHT_TOKENS} />
      <Swatches title="Dark palette" tokens={DARK_TOKENS} />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Type — Plus Jakarta Sans</h2>
        <div className="rounded-card border border-border bg-surface p-5">
          {SANS_WEIGHTS.map((weight) => (
            <p key={weight} className="text-xl" style={{ fontWeight: weight }}>
              {weight} — Receivables ageing ₹12,34,567.89 · GSTR-3B due 20 Oct
            </p>
          ))}
        </div>
        <h2 className="text-lg font-semibold">Type — Instrument Serif italic (display only)</h2>
        <div className="rounded-card border border-border bg-surface p-5">
          <p className="font-display text-4xl italic">400 italic — Cashflow, forecast.</p>
          <p className="mt-2 font-display text-3xl italic tabular-nums">₹1,23,45,678.90</p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">MoneyText</h2>
        <div className="flex flex-wrap gap-6 rounded-card border border-border bg-surface p-5 text-lg">
          {SAMPLE_MONEY.map((value) => (
            <div key={value} className="space-y-1">
              <MoneyText value={value} />
              <p className="text-xs text-muted">
                abbreviate: <MoneyText value={value} abbreviate />
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">StatTile</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatTile label="Cash position" value="₹42,18,560.00" delta={{ value: "+8.2%", direction: "up" }} hint="vs last month" />
          <StatTile label="Payables" value="₹9,80,120.50" delta={{ value: "-3.1%", direction: "down" }} hint="30 days" />
          <StatTile label="Runway" value="11.4 months" delta={{ value: "0.0%", direction: "flat" }} hint="P50 forecast" />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">PeriodPicker · BasisBadge</h2>
        <div className="space-y-4 rounded-card border border-border bg-surface p-5">
          <PeriodPickerDemo />
          <div className="flex gap-3">
            <BasisBadge basis="accrual" pendingCount={12} />
            <BasisBadge basis="cash" pendingCount={0} />
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Buttons · Badges · Inputs · Skeleton</h2>
        <div className="space-y-4 rounded-card border border-border bg-surface p-5">
          <div className="flex flex-wrap gap-3">
            <Button>Primary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="link">Link</Button>
          </div>
          <div className="flex flex-wrap gap-3">
            <Badge>Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="outline">Outline</Badge>
            <Badge variant="destructive">Destructive</Badge>
            <Badge variant="outline" className="border-success text-success">Confirmed</Badge>
            <Badge variant="outline" className="border-warning text-warning">Needs review</Badge>
            <Badge variant="outline" className="border-info text-info">In 2B</Badge>
          </div>
          <Input placeholder="Search invoices…" className="max-w-xs" />
          <Skeleton className="h-6 w-1/2" />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">EmptyState · ErrorBoundary</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          <EmptyState
            icon={Inbox}
            title="No threads yet"
            description="Connect a mailbox in Settings to start triaging client email."
            action={<Button variant="outline">Connect mailbox</Button>}
          />
          <ErrorBoundaryDemo />
        </div>
        <EmptyState icon={FileText} title="Compact variant" className="py-6" />
      </section>
    </div>
  );
}
