"use client";

import { Bell, Check, Landmark, Mail, X } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { useStatementImports } from "@/lib/bank";
import { ICON_STROKE } from "@/lib/constants";
import { formatDate, timeAgo } from "@/lib/format";
import { useMailboxes } from "@/lib/mail";
import { useNotificationAction, useNotifications } from "@/lib/notifications";
import type { Notification } from "@/lib/types";
import { cn } from "@/lib/utils";

const NOTIFICATION_LIMIT = 5;
const LEVEL_CLASS: Record<Notification["level"], string> = { info: "text-muted", warning: "text-warning", danger: "text-danger" };

/** Mailbox sync, last statement import and open reminders — the "is everything still connected" row. */
export function ConnectionsPanel() {
  const mailboxes = useMailboxes();
  const imports = useStatementImports();
  const notifications = useNotifications();
  const act = useNotificationAction();
  const latestImport = imports.data?.results[0];
  const open = notifications.data ?? [];
  const unread = open.filter((note) => note.read_at === null);

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card icon={Mail} title="Mailbox" href="/settings?tab=mail" linkLabel="Mail settings">
        {mailboxes.isPending && <p className="text-xs text-muted">Loading…</p>}
        {mailboxes.data?.length === 0 && <p className="text-sm text-muted">No mailbox connected.</p>}
        {mailboxes.data?.map((mailbox) => (
          <div key={mailbox.id} className="space-y-1">
            <p className="truncate text-sm font-medium">{mailbox.email_address}</p>
            <p className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <StatusBadge status={mailbox.status} />
              <span>synced {timeAgo(mailbox.last_sync_at)}</span>
            </p>
            {mailbox.last_error && <p className="break-words text-xs text-danger">{mailbox.last_error}</p>}
          </div>
        ))}
      </Card>

      <Card icon={Landmark} title="Bank statements" href="/bank" linkLabel="Bank &amp; matching">
        {imports.isPending && <p className="text-xs text-muted">Loading…</p>}
        {imports.data && !latestImport && <p className="text-sm text-muted">No statement imported yet.</p>}
        {latestImport && (
          <div className="space-y-1">
            <p className="truncate text-sm font-medium">{latestImport.filename}</p>
            <p className="text-xs text-muted">
              {latestImport.rows_imported} new · {latestImport.rows_duplicate} duplicate of {latestImport.rows_total} · {latestImport.mapping.toUpperCase()}
            </p>
            <p className="text-xs text-muted">{formatDate(latestImport.created_at.slice(0, 10))}</p>
          </div>
        )}
      </Card>

      <Card icon={Bell} title={unread.length > 0 ? `Reminders (${unread.length} new)` : "Reminders"}>
        {notifications.isPending && <p className="text-xs text-muted">Loading…</p>}
        {notifications.data && open.length === 0 && <p className="text-sm text-muted">Nothing needs attention.</p>}
        <ul className="divide-y divide-border">
          {open.slice(0, NOTIFICATION_LIMIT).map((note) => (
            <li key={note.id} className="flex items-start gap-2 py-2">
              <span className="min-w-0 flex-1">
                <span className={cn("block text-sm", note.read_at === null && "font-medium", LEVEL_CLASS[note.level])}>{note.title}</span>
                <span className="block text-xs text-muted">{note.body}</span>
              </span>
              {note.read_at === null && (
                <Button variant="ghost" size="icon" aria-label={`Mark read: ${note.title}`} onClick={() => act.mutate({ id: note.id, action: "read" })}>
                  <Check size={14} strokeWidth={ICON_STROKE} aria-hidden />
                </Button>
              )}
              <Button variant="ghost" size="icon" aria-label={`Dismiss: ${note.title}`} onClick={() => act.mutate({ id: note.id, action: "dismiss" })}>
                <X size={14} strokeWidth={ICON_STROKE} aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function Card({ icon: Icon, title, href, linkLabel, children }: { icon: typeof Mail; title: string; href?: string; linkLabel?: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="flex min-w-0 flex-col gap-3 rounded-card border border-border bg-surface p-5">
      <header className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Icon size={16} strokeWidth={ICON_STROKE} className="text-muted" aria-hidden /> {title}
        </h2>
        {href && (
          <Link href={href} className="text-xs text-accent hover:underline">
            {linkLabel}
          </Link>
        )}
      </header>
      {children}
    </section>
  );
}
