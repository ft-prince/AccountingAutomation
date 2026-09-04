"use client";

import { FileUp } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/primitives/page-header";
import { QueryState } from "@/components/primitives/query-state";
import { Button } from "@/components/ui/button";
import { useBankAccounts } from "@/lib/bank";
import { ICON_STROKE } from "@/lib/constants";
import { AccountsPanel } from "./accounts-panel";
import { ImportWizard } from "./import-wizard";
import { MatchQueue } from "./match-queue";

export function BankView() {
  const accounts = useBankAccounts();
  const [accountId, setAccountId] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const list = accounts.data?.results ?? [];

  useEffect(() => {
    if (accountId === "" && list.length > 0) setAccountId(list[0].id);
  }, [accountId, list]);

  return (
    <div className="space-y-8">
      <PageHeader
        title="Bank &"
        emphasis="matching"
        description="Import statements, then match each transaction to invoices. Matched rows become payments."
        actions={
          <Button onClick={() => setIsImporting(true)} disabled={list.length === 0}>
            <FileUp strokeWidth={ICON_STROKE} aria-hidden /> Import statement
          </Button>
        }
      />
      <QueryState isPending={accounts.isPending} error={accounts.error} onRetry={() => accounts.refetch()} skeletonClassName="h-32 w-full">
        <AccountsPanel accounts={list} selectedId={accountId} onSelect={setAccountId} />
      </QueryState>
      {accountId !== "" && <MatchQueue accountId={accountId} />}
      {isImporting && <ImportWizard accounts={list} defaultAccountId={accountId} open onOpenChange={setIsImporting} onImported={() => undefined} />}
    </div>
  );
}
