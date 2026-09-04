"use client";

import { Paperclip, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ICON_STROKE } from "@/lib/constants";
import type { MailMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

interface AttachmentLike {
  filename?: string;
  name?: string;
  size?: number;
}

function attachmentNames(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((entry) => {
    if (typeof entry === "string") return entry;
    const item = entry as AttachmentLike;
    return item.filename ?? item.name ?? "attachment";
  });
}

function MessageCard({ message }: { message: MailMessage }) {
  // body_html is sanitised server-side (apps/mail/sanitize.py) before it is ever stored; the
  // toggle lets the reviewer fall back to plain text when the HTML hides something.
  const [showHtml, setShowHtml] = useState(Boolean(message.body_html));
  const isOutbound = message.direction === "outbound";
  const attachments = attachmentNames(message.attachments);
  return (
    <article className={cn("rounded-card border border-border bg-surface p-4", isOutbound && "border-accent/40")} data-direction={message.direction}>
      <header className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-muted">
        <span>
          <span className="font-medium text-foreground">{message.from_address}</span>
          {message.to_addresses && message.to_addresses.length > 0 && ` → ${message.to_addresses.join(", ")}`}
        </span>
        <span className="tabular-nums">{new Date(message.date).toLocaleString("en-IN")}</span>
      </header>
      {message.injection_flag && (
        <div role="alert" className="mt-3 flex items-start gap-2 rounded-md border border-warning px-3 py-2 text-xs text-warning">
          <ShieldAlert size={14} strokeWidth={ICON_STROKE} className="mt-0.5 shrink-0" aria-hidden />
          <span>
            <strong>Instructions inside this email were ignored.</strong> Text in inbound mail is data, not commands (CLAUDE.md §4).
            {message.injection_note && ` ${message.injection_note}`}
          </span>
        </div>
      )}
      <div className="mt-3">
        {showHtml && message.body_html ? (
          <div className="prose prose-sm max-w-none text-sm text-foreground" dangerouslySetInnerHTML={{ __html: message.body_html }} />
        ) : (
          <pre className="whitespace-pre-wrap font-sans text-sm leading-6">{message.body_text || "(empty message)"}</pre>
        )}
      </div>
      <footer className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
        {message.body_html && (
          <Button variant="ghost" size="sm" onClick={() => setShowHtml((value) => !value)}>
            {showHtml ? "Show plain text" : "Show HTML"}
          </Button>
        )}
        {attachments.map((name) => (
          <span key={name} className="inline-flex items-center gap-1">
            <Paperclip size={12} strokeWidth={ICON_STROKE} aria-hidden /> {name}
          </span>
        ))}
      </footer>
    </article>
  );
}

export function MessageList({ messages }: { messages: readonly MailMessage[] }) {
  if (messages.length === 0) return <p className="text-sm text-muted">No messages in this thread yet.</p>;
  return (
    <div className="space-y-3" aria-label="Messages">
      {messages.map((message) => (
        <MessageCard key={message.id} message={message} />
      ))}
    </div>
  );
}
