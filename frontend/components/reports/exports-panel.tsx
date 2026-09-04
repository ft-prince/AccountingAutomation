"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { Field } from "@/components/primitives/field";
import { Input } from "@/components/ui/input";
import { ICON_STROKE } from "@/lib/constants";
import { CSV_EXPORT_TYPES, csvExportUrl, gstr1ExportUrl, gstr3bExportUrl, toGstPeriod } from "@/lib/exports";

const LINK_CLASS =
  "inline-flex h-9 items-center gap-2 rounded-full border border-border bg-surface px-4 text-sm transition-colors duration-150 hover:border-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

/** §10 Exports — GSTR-1 / GSTR-3B JSON for one month, CSV for Tally / Zoho / raw. Server responses are confirmed-only. */
export function ExportsPanel({ defaultMonth, range }: { defaultMonth: string; range: { from: string; to: string } }) {
  const [month, setMonth] = useState(defaultMonth.slice(0, 7)); // YYYY-MM
  const period = /^\d{4}-\d{2}$/.test(month) ? toGstPeriod(`${month}-01`) : null;

  return (
    <section aria-label="Exports" className="flex flex-wrap items-end gap-3 rounded-card border border-border bg-surface p-4">
      <Field id="export-month" label="GST return month" hint="Confirmed invoices only; pending count is sent in X-Pending-Count.">
        <Input id="export-month" type="month" value={month} onChange={(event) => setMonth(event.target.value)} className="w-44" />
      </Field>
      {period && (
        <>
          <a className={LINK_CLASS} href={gstr1ExportUrl(period)} download>
            <Download size={16} strokeWidth={ICON_STROKE} aria-hidden /> GSTR-1 JSON
          </a>
          <a className={LINK_CLASS} href={gstr3bExportUrl(period)} download>
            <Download size={16} strokeWidth={ICON_STROKE} aria-hidden /> GSTR-3B JSON
          </a>
        </>
      )}
      <span className="mx-1 hidden h-6 w-px bg-border sm:block" aria-hidden />
      {CSV_EXPORT_TYPES.map((type) => (
        <a key={type} className={LINK_CLASS} href={csvExportUrl(type, range)} download>
          <Download size={16} strokeWidth={ICON_STROKE} aria-hidden /> {type === "raw" ? "Raw CSV" : `${type[0].toUpperCase()}${type.slice(1)} CSV`}
        </a>
      ))}
    </section>
  );
}
