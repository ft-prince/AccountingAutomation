"use client";

import { Mail, Plus } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/primitives/empty-state";
import { Field } from "@/components/primitives/field";
import { NativeSelect } from "@/components/primitives/native-select";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { useConnectMailbox, useCreateTemplate, useGrantSendScope, useMailboxes, useRevokeMailbox, useSaveStyleGuide, useStyleGuide, useTemplates } from "@/lib/mail";
import { toastApiError } from "@/lib/toast";
import type { Intent, MailProvider, StyleGuide } from "@/lib/types";

const PROVIDERS: readonly { value: MailProvider; label: string }[] = [
  { value: "gmail", label: "Gmail" },
  { value: "microsoft", label: "Microsoft 365" },
];
const INTENTS: readonly Intent[] = ["invoice_query", "payment_confirmation", "payment_delay_notice", "statement_request", "quote_request", "po_or_order", "dispute", "vendor_bill_received", "support", "meeting_or_scheduling", "newsletter_or_spam", "other"];
const TEXTAREA_CLASS = "min-h-[6rem] w-full rounded-card border border-input bg-surface p-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-60";

function openAuthorization(url: string): void {
  window.open(url, "_blank", "noopener,noreferrer");
}

/** The OAuth callback lands the browser on /settings?tab=mail&connected=… or &mailbox_error=…. */
function useCallbackOutcome(): void {
  const params = useSearchParams();
  const router = useRouter();
  const connected = params.get("connected");
  const error = params.get("mailbox_error");
  useEffect(() => {
    if (!connected && !error) return;
    if (connected) toast({ title: `Connected ${connected}`, description: "First sync runs within two minutes." });
    if (error) toast({ title: "Mailbox not connected", description: error, variant: "destructive" });
    router.replace("/settings?tab=mail");
  }, [connected, error, router]);
}

function MailboxesSection({ isOwner }: { isOwner: boolean }) {
  useCallbackOutcome();
  const mailboxes = useMailboxes();
  const connect = useConnectMailbox();
  const revoke = useRevokeMailbox();
  const grant = useGrantSendScope();
  const [provider, setProvider] = useState<MailProvider>("gmail");

  const startConnect = () =>
    connect.mutate(provider, {
      onSuccess: (response) => { openAuthorization(response.authorization_url); toast({ title: "Continue in the provider window", description: "The mailbox appears here once authorised." }); },
      onError: (error) => toastApiError(error, "Could not start connection"),
    });

  return (
    <section aria-label="Mailboxes" className="space-y-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Mailboxes</h2>
        {isOwner && (
          <div className="flex items-center gap-2">
            <NativeSelect aria-label="Provider" value={provider} onChange={(event) => setProvider(event.target.value as MailProvider)}>
              {PROVIDERS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </NativeSelect>
            <Button onClick={startConnect} disabled={connect.isPending}>
              <Plus strokeWidth={ICON_STROKE} aria-hidden /> Connect
            </Button>
          </div>
        )}
      </header>
      <QueryState isPending={mailboxes.isPending} error={mailboxes.error} onRetry={() => void mailboxes.refetch()}>
        {mailboxes.data?.length === 0 ? (
          <EmptyState icon={Mail} title="No mailbox connected" description="Read scope is requested first; the send scope is a separate, later grant (§12)." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Address</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Send scope</TableHead>
                <TableHead>Last sync</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {mailboxes.data?.map((mailbox) => (
                <TableRow key={mailbox.id}>
                  <TableCell className="font-medium">{mailbox.email_address}</TableCell>
                  <TableCell>{mailbox.provider}</TableCell>
                  <TableCell>
                    <StatusBadge status={mailbox.status} />
                    {mailbox.last_error && <span className="ml-2 text-xs text-danger">{mailbox.last_error}</span>}
                  </TableCell>
                  <TableCell>
                    {mailbox.has_send_scope ? (
                      <StatusBadge status="granted" tone="success" label="Granted" />
                    ) : (
                      <span className="flex items-center gap-2">
                        <StatusBadge status="missing" tone="warning" label={mailbox.needs_send_scope ? "Needed" : "Not granted"} />
                        {isOwner && mailbox.status === "active" && (
                          <Button variant="outline" size="sm" disabled={grant.isPending} onClick={() => grant.mutate(mailbox.id, { onSuccess: (response) => openAuthorization(response.authorization_url), onError: (error) => toastApiError(error, "Could not request send scope") })}>
                            Grant send scope
                          </Button>
                        )}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted tabular-nums">{mailbox.last_sync_at ? formatDate(mailbox.last_sync_at) : "never"}</TableCell>
                  <TableCell className="text-right">
                    {isOwner && mailbox.status !== "revoked" && (
                      <Button variant="ghost" size="sm" disabled={revoke.isPending} onClick={() => revoke.mutate(mailbox.id, { onSuccess: () => toast({ title: "Mailbox revoked" }), onError: (error) => toastApiError(error, "Revoke failed") })}>
                        Revoke
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
    </section>
  );
}

type GuideForm = { sign_off: string; tone_rules: string; banned_phrases: string; must_include: string };

function toForm(guide: StyleGuide | undefined): GuideForm {
  return { sign_off: guide?.sign_off ?? "", tone_rules: guide?.tone_rules ?? "", banned_phrases: (guide?.banned_phrases ?? []).join("\n"), must_include: (guide?.must_include ?? []).join("\n") };
}

function lines(text: string): string[] {
  return text.split("\n").map((line) => line.trim()).filter((line) => line.length > 0);
}

function StyleGuideSection({ isOwner }: { isOwner: boolean }) {
  const guide = useStyleGuide();
  const save = useSaveStyleGuide();
  const [form, setForm] = useState<GuideForm>(() => toForm(undefined));
  useEffect(() => { if (guide.data) setForm(toForm(guide.data)); }, [guide.data]);
  const set = (key: keyof GuideForm, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const examples = Array.isArray(guide.data?.few_shot_examples) ? guide.data.few_shot_examples.length : 0;

  return (
    <section aria-label="Style guide" className="space-y-3">
      <h2 className="text-sm font-semibold">Style guide</h2>
      <QueryState isPending={guide.isPending} error={guide.error} onRetry={() => void guide.refetch()}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="sg-signoff" label="Sign-off" className="sm:col-span-2">
            <Input id="sg-signoff" value={form.sign_off} disabled={!isOwner} onChange={(event) => set("sign_off", event.target.value)} />
          </Field>
          <Field id="sg-tone" label="Tone rules" className="sm:col-span-2">
            <textarea id="sg-tone" className={TEXTAREA_CLASS} value={form.tone_rules} disabled={!isOwner} onChange={(event) => set("tone_rules", event.target.value)} />
          </Field>
          <Field id="sg-banned" label="Banned phrases" hint="One per line">
            <textarea id="sg-banned" className={TEXTAREA_CLASS} value={form.banned_phrases} disabled={!isOwner} onChange={(event) => set("banned_phrases", event.target.value)} />
          </Field>
          <Field id="sg-must" label="Must include" hint="One per line">
            <textarea id="sg-must" className={TEXTAREA_CLASS} value={form.must_include} disabled={!isOwner} onChange={(event) => set("must_include", event.target.value)} />
          </Field>
        </div>
        <p className="text-xs text-muted">{examples} few-shot example{examples === 1 ? "" : "s"} · updated {guide.data?.updated_at ? formatDate(guide.data.updated_at) : "never"}</p>
        {isOwner && (
          <Button
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                { sign_off: form.sign_off, tone_rules: form.tone_rules, banned_phrases: lines(form.banned_phrases), must_include: lines(form.must_include), few_shot_examples: guide.data?.few_shot_examples ?? [] },
                { onSuccess: () => toast({ title: "Style guide saved" }), onError: (error) => toastApiError(error, "Could not save style guide") },
              )
            }
          >
            {save.isPending ? "Saving…" : "Save style guide"}
          </Button>
        )}
      </QueryState>
    </section>
  );
}

function TemplateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const create = useCreateTemplate();
  const [form, setForm] = useState<{ intent: Intent; name: string; body: string }>({ intent: "invoice_query", name: "", body: "" });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New reply template</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4">
          <Field id="tpl-intent" label="Intent">
            <NativeSelect id="tpl-intent" value={form.intent} onChange={(event) => setForm({ ...form, intent: event.target.value as Intent })}>
              {INTENTS.map((intent) => (
                <option key={intent} value={intent}>{intent.replace(/_/g, " ")}</option>
              ))}
            </NativeSelect>
          </Field>
          <Field id="tpl-name" label="Name" required>
            <Input id="tpl-name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </Field>
          <Field id="tpl-body" label="Body" required hint="Bank details never go in a template the model sees; the reviewer inserts them (§6.5).">
            <textarea id="tpl-body" className={TEXTAREA_CLASS} value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} />
          </Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={!form.name || !form.body || create.isPending} onClick={() => create.mutate(form, { onSuccess: () => { toast({ title: "Template created" }); onOpenChange(false); }, onError: (error) => toastApiError(error, "Could not create template") })}>
            {create.isPending ? "Saving…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TemplatesSection({ canEdit }: { canEdit: boolean }) {
  const templates = useTemplates();
  const [isCreating, setIsCreating] = useState(false);
  return (
    <section aria-label="Reply templates" className="space-y-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Reply templates</h2>
        {canEdit && (
          <Button variant="outline" onClick={() => setIsCreating(true)}>
            <Plus strokeWidth={ICON_STROKE} aria-hidden /> New template
          </Button>
        )}
      </header>
      <QueryState isPending={templates.isPending} error={templates.error} onRetry={() => void templates.refetch()}>
        {templates.data?.length === 0 ? (
          <p className="text-sm text-muted">No templates yet. The drafter falls back to the style guide alone.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Intent</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Body</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.data?.map((template) => (
                <TableRow key={template.id}>
                  <TableCell>{template.intent.replace(/_/g, " ")}</TableCell>
                  <TableCell className="font-medium">{template.name}</TableCell>
                  <TableCell className="max-w-md truncate text-muted">{template.body}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </QueryState>
      {isCreating && <TemplateDialog open onOpenChange={setIsCreating} />}
    </section>
  );
}

/** §11 /settings mail: mailboxes (owner connects/revokes), style guide (owner edits), templates. */
export function MailTab({ isOwner, canEdit }: { isOwner: boolean; canEdit: boolean }) {
  return (
    <div className="space-y-8">
      <MailboxesSection isOwner={isOwner} />
      <StyleGuideSection isOwner={isOwner} />
      <TemplatesSection canEdit={canEdit} />
    </div>
  );
}
