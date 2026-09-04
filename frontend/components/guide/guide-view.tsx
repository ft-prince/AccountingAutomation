import { Download, ExternalLink } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/primitives/page-header";
import { ALL_SAMPLES, DEMO_LOGIN, MODULES, SAMPLE_DIR, type GuideModule } from "@/lib/guide";
import { ICON_STROKE } from "@/lib/constants";

const CARD = "rounded-card border border-border bg-surface p-5";

function OrderedList({ items, className }: { items: readonly string[]; className?: string }) {
  return (
    <ol className={`ml-4 list-decimal space-y-1.5 text-sm text-muted marker:text-muted ${className ?? ""}`}>
      {items.map((item) => (
        <li key={item} className="pl-1">
          {item}
        </li>
      ))}
    </ol>
  );
}

function SampleRow({ file, label, demonstrates, target }: { file: string; label: string; demonstrates: string; target: string }) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-border py-3 first:border-t-0 first:pt-0">
      <a
        href={`${SAMPLE_DIR}/${file}`}
        download
        className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-border px-3 py-1 text-sm font-medium transition duration-150 hover:-translate-y-0.5 hover:border-ink-muted"
      >
        <Download size={14} strokeWidth={ICON_STROKE} aria-hidden />
        {label}
      </a>
      <span className="min-w-0 flex-1 text-sm text-muted">{demonstrates}</span>
      <span className="shrink-0 text-xs uppercase tracking-wide text-muted">{target}</span>
    </li>
  );
}

function ModuleSection({ module: mod }: { module: GuideModule }) {
  return (
    <section id={mod.id} className="scroll-mt-6 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-xl font-semibold tracking-tight">{mod.title}</h2>
        <Link href={mod.route} className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline">
          Open {mod.route}
          <ExternalLink size={14} strokeWidth={ICON_STROKE} aria-hidden />
        </Link>
      </div>

      <p className="max-w-3xl text-base">{mod.what}</p>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className={CARD}>
          <h3 className="text-sm font-semibold">How it works</h3>
          <ul className="mt-3 space-y-2 text-sm text-muted">
            {mod.how.map((line) => (
              <li key={line} className="border-l border-border pl-3">
                {line}
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-4">
          <div className={CARD}>
            <h3 className="text-sm font-semibold">When to use it</h3>
            <p className="mt-2 text-sm text-muted">{mod.when}</p>
          </div>
          <div className={CARD}>
            <h3 className="text-sm font-semibold">Try it</h3>
            <OrderedList items={mod.steps} className="mt-3" />
          </div>
        </div>
      </div>

      {mod.samples.length > 0 && (
        <div className={CARD}>
          <h3 className="text-sm font-semibold">Sample files</h3>
          <ul className="mt-3">
            {mod.samples.map((sample) => (
              <SampleRow key={sample.file} {...sample} />
            ))}
          </ul>
        </div>
      )}

      {mod.caveat && (
        <p className="rounded-card border border-warning/40 bg-warning/5 p-4 text-sm text-muted">
          <span className="font-medium text-foreground">Before this works: </span>
          {mod.caveat}
        </p>
      )}
    </section>
  );
}

export function GuideView() {
  return (
    <div className="space-y-10 pb-16">
      <PageHeader
        title="How this"
        emphasis="works"
        description="What each part of Nexren Finance does, when you would reach for it, and a sample document to test it with."
      />

      <section className={`${CARD} space-y-4`}>
        <h2 className="text-sm font-semibold">Start here</h2>
        <p className="text-sm text-muted">
          Sign in as{" "}
          <span className="font-medium text-foreground">
            {DEMO_LOGIN.email} / {DEMO_LOGIN.password}
          </span>
          . The demo organisation already holds fifteen months of history: thirty parties with
          different payment habits, around five hundred invoices, matching payments, a bank
          statement, twelve invoices waiting in Review and a few deliberately broken ones.
        </p>
        <p className="text-sm text-muted">
          Three human gates are the point of the product. Nothing an AI produced reaches a confirmed
          state on its own: an invoice is confirmed by a person, an email draft is approved and sent
          by a person, and a forecast shows its own backtest score so nobody mistakes it for a
          prediction.
        </p>
        <nav className="flex flex-wrap gap-2 pt-1">
          {MODULES.map((mod) => (
            <a
              key={mod.id}
              href={`#${mod.id}`}
              className="rounded-full border border-border px-3 py-1 text-sm transition duration-150 hover:-translate-y-0.5 hover:border-ink-muted"
            >
              {mod.title}
            </a>
          ))}
          <a
            href="#downloads"
            className="rounded-full border border-border px-3 py-1 text-sm transition duration-150 hover:-translate-y-0.5 hover:border-ink-muted"
          >
            All downloads
          </a>
        </nav>
      </section>

      {MODULES.map((mod) => (
        <ModuleSection key={mod.id} module={mod} />
      ))}

      <section id="downloads" className="scroll-mt-6 space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">All sample documents</h2>
        <p className="max-w-3xl text-sm text-muted">
          Every file is generated from the same rules the application enforces, so the numbers
          reconcile exactly. The three vendor bills and the GSTR-2B download are written to line up
          with each other, so uploading the bills first makes the reconciliation produce one of every
          match type.
        </p>
        <div className={CARD}>
          <ul>
            {ALL_SAMPLES.map((sample) => (
              <SampleRow key={sample.file} {...sample} />
            ))}
          </ul>
        </div>
      </section>

      <section className={`${CARD} space-y-2`}>
        <h2 className="text-sm font-semibold">What needs your credentials</h2>
        <p className="text-sm text-muted">
          Extraction, email classification, drafting and the forecast summary all call the Anthropic
          API and need <span className="font-medium text-foreground">ANTHROPIC_API_KEY</span> in{" "}
          <span className="font-medium text-foreground">.env</span>. Connecting a mailbox needs
          Google or Microsoft OAuth client credentials. Set a monthly spend cap before pointing any
          of it at a real inbox or a real folder of invoices. Keys belong in the environment file
          only, never in code or a chat window.
        </p>
      </section>
    </div>
  );
}
