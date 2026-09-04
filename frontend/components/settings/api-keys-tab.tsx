"use client";

import { Copy, KeyRound, Plus } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "@/components/primitives/confirm-dialog";
import { EmptyState } from "@/components/primitives/empty-state";
import { Field } from "@/components/primitives/field";
import { QueryState } from "@/components/primitives/query-state";
import { StatusBadge } from "@/components/primitives/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/hooks/use-toast";
import { ICON_STROKE } from "@/lib/constants";
import { useApiKeys, useCreateApiKey, useRevokeApiKey, type CreatedApiKey } from "@/lib/settings";
import { toastApiError } from "@/lib/toast";
import type { ApiKey } from "@/lib/types";

/** The raw key is shown exactly once (§12: API keys are server-side only afterwards). */
function CreatedKeyDialog({ created, onClose }: { created: CreatedApiKey; onClose: () => void }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(created.key);
      toast({ title: "Copied to clipboard" });
    } catch {
      toast({ variant: "destructive", title: "Clipboard unavailable", description: "Select the key and copy it manually." });
    }
  };
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>API key “{created.name}”</DialogTitle>
          <DialogDescription>Copy it now. It is shown once and cannot be retrieved again; only the prefix is stored.</DialogDescription>
        </DialogHeader>
        <code data-testid="raw-api-key" className="block break-all rounded-card border border-border bg-background p-3 text-sm">
          {created.key}
        </code>
        <DialogFooter>
          <Button variant="outline" onClick={copy}>
            <Copy size={16} strokeWidth={ICON_STROKE} aria-hidden /> Copy
          </Button>
          <Button onClick={onClose}>I have saved it</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ApiKeysTab({ isOwner }: { isOwner: boolean }) {
  const keys = useApiKeys();
  const create = useCreateApiKey();
  const revoke = useRevokeApiKey();
  const [name, setName] = useState("");
  const [created, setCreated] = useState<CreatedApiKey | null>(null);
  const [revoking, setRevoking] = useState<ApiKey | null>(null);

  const submit = () =>
    create.mutate(name.trim(), {
      onSuccess: (key) => {
        setCreated(key);
        setName("");
      },
      onError: (error) => toastApiError(error, "Could not create API key"),
    });

  const confirmRevoke = () => {
    if (!revoking) return;
    revoke.mutate(revoking.id, {
      onSuccess: () => {
        toast({ title: "API key revoked" });
        setRevoking(null);
      },
      onError: (error) => toastApiError(error, "Could not revoke API key"),
    });
  };

  return (
    <div className="space-y-4">
      {isOwner ? (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <Field id="api-key-name" label="Key name" required hint="e.g. Tally sync, Zapier">
            <Input id="api-key-name" value={name} onChange={(event) => setName(event.target.value)} className="w-64" />
          </Field>
          <Button type="submit" disabled={name.trim() === "" || create.isPending}>
            <Plus size={16} strokeWidth={ICON_STROKE} aria-hidden /> {create.isPending ? "Creating…" : "Create key"}
          </Button>
        </form>
      ) : (
        <p className="text-sm text-muted">Only owners can create or revoke API keys.</p>
      )}
      <QueryState isPending={keys.isPending} error={keys.error} onRetry={() => void keys.refetch()}>
        {keys.data?.length === 0 ? (
          <EmptyState icon={KeyRound} title="No API keys" description="Keys authenticate integrations with the X-API-Key header." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Prefix</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Last used</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {keys.data?.map((key) => (
                <TableRow key={key.id}>
                  <TableCell>{key.name}</TableCell>
                  <TableCell className="font-mono text-xs">{key.prefix}…</TableCell>
                  <TableCell className="text-muted">{key.created_at.slice(0, 10)}</TableCell>
                  <TableCell className="text-muted">{key.last_used_at?.slice(0, 10) ?? "never"}</TableCell>
                  <TableCell>{key.revoked_at ? <StatusBadge status="revoked" tone="muted" /> : <StatusBadge status="active" tone="success" />}</TableCell>
                  <TableCell className="text-right">
                    {isOwner && !key.revoked_at && (
                      <Button variant="ghost" size="sm" className="text-danger" onClick={() => setRevoking(key)}>
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
      {created && <CreatedKeyDialog created={created} onClose={() => setCreated(null)} />}
      <ConfirmDialog
        open={revoking !== null}
        onOpenChange={(open) => !open && setRevoking(null)}
        title={`Revoke “${revoking?.name ?? ""}”?`}
        description="Integrations using this key stop working immediately."
        confirmLabel="Revoke"
        destructive
        isPending={revoke.isPending}
        onConfirm={confirmRevoke}
      />
    </div>
  );
}
