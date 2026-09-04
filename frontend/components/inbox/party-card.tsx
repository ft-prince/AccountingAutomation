"use client";

import Link from "next/link";
import { MoneyText } from "@/components/primitives/money-text";
import { RiskBandBadge } from "@/components/primitives/risk-band-badge";
import { useCustomerRisk } from "@/lib/forecast";
import { formatDate } from "@/lib/format";
import { usePayments } from "@/lib/payments";
import { resolvePeriod, todayIso } from "@/lib/periods";
import { AGING_BUCKETS, useReport } from "@/lib/reports";

/** §6.6 party card: open balance, aging, last payment, plus the §8.5 risk band. */
export function PartyCard({ partyId, partyName }: { partyId: string | null | undefined; partyName: string }) {
  const period = resolvePeriod("fy_to_date", todayIso());
  const enabled = Boolean(partyId);
  const arAging = useReport("ar-aging", { from: period.from, to: period.to, basis: "accrual" }, enabled);
  const payments = usePayments({ party: partyId ?? "" }, enabled);
  const risk = useCustomerRisk(enabled);
  const row = arAging.data?.rows.find((entry) => entry.party === partyId);
  const lastPayment = payments.data?.results[0];
  const band = risk.data?.find((entry) => entry.party === partyId)?.band;

  return (
    <section aria-label="Party" className="rounded-card border border-border bg-surface p-4">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-muted">Party</p>
          {partyId ? (
            <Link href={`/parties/${partyId}`} className="truncate text-sm font-semibold hover:text-accent">{partyName || "Unnamed party"}</Link>
          ) : (
            <p className="text-sm font-semibold text-warning">Unresolved</p>
          )}
        </div>
        {partyId && <RiskBandBadge band={band} />}
      </header>
      {partyId ? (
        <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
          <dt className="text-xs text-muted">Open balance</dt>
          <dd className="text-right font-medium"><MoneyText value={row?.total ?? "0"} /></dd>
          {AGING_BUCKETS.map((bucket) => (
            <div key={bucket} className="contents">
              <dt className="text-xs text-muted">{bucket} d</dt>
              <dd className="text-right"><MoneyText value={row?.[bucket] ?? "0"} /></dd>
            </div>
          ))}
          <dt className="text-xs text-muted">Last payment</dt>
          <dd className="text-right">
            {lastPayment ? (
              <>
                <MoneyText value={lastPayment.amount ?? "0"} /> <span className="text-xs text-muted">· {formatDate(lastPayment.date)}</span>
              </>
            ) : (
              <span className="text-muted">none</span>
            )}
          </dd>
        </dl>
      ) : (
        <p className="mt-2 text-xs text-muted">The sender could not be matched to a party; the draft is flagged party_unresolved.</p>
      )}
    </section>
  );
}
