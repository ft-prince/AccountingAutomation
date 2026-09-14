"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { buildQuery, type Paginated } from "@/lib/query";
import type { BankAccount, BankTransaction, MatchStatus, StatementImport } from "@/lib/types";

export const BANK_KEY = "bank";
const TRANSACTIONS_PAGE_SIZE = 100;

export const BANK_MAPPINGS = ["auto", "hdfc", "icici", "sbi", "axis", "kotak", "generic"] as const;
export type BankMapping = (typeof BANK_MAPPINGS)[number];

export function useBankAccounts() {
  return useQuery({ queryKey: [BANK_KEY, "accounts"], queryFn: () => api<Paginated<BankAccount>>("/api/bank/accounts/") });
}

export type BankAccountInput = Pick<BankAccount, "name" | "bank" | "masked_account" | "opening_balance" | "opening_balance_date" | "is_active">;

export function useSaveBankAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id?: string; body: BankAccountInput }) =>
      input.id
        ? api<BankAccount>(`/api/bank/accounts/${input.id}/`, { method: "PATCH", body: JSON.stringify(input.body) })
        : api<BankAccount>("/api/bank/accounts/", { method: "POST", body: JSON.stringify(input.body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [BANK_KEY, "accounts"] }),
  });
}

export interface ImportResult {
  rows_total: number;
  rows_imported: number;
  rows_duplicate: number;
  mapping: string;
}

export function useImportStatement() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; account: string; mapping: BankMapping; password?: string }) => {
      const form = new FormData();
      form.append("file", input.file);
      form.append("account", input.account);
      if (input.mapping !== "auto") form.append("mapping", input.mapping);
      if (input.password) form.append("password", input.password);
      return api<ImportResult>("/api/bank/statements/import", { method: "POST", body: form });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [BANK_KEY] }),
  });
}

const IMPORT_HISTORY_SIZE = 10;

export function useStatementImports() {
  return useQuery({
    queryKey: [BANK_KEY, "imports"],
    queryFn: () => api<Paginated<StatementImport>>(`/api/bank/statements/${buildQuery({ page_size: IMPORT_HISTORY_SIZE })}`),
  });
}

export function useBankTransactions(status: MatchStatus | "", account: string) {
  return useQuery({
    queryKey: [BANK_KEY, "transactions", status, account],
    queryFn: () =>
      api<Paginated<BankTransaction>>(`/api/bank/transactions/${buildQuery({ status, account, page_size: TRANSACTIONS_PAGE_SIZE })}`),
  });
}

export interface MatchCandidateInvoice {
  id: string;
  invoice_number: string;
  party: string;
  outstanding: string;
  due_date: string | null;
}
export interface MatchCandidate {
  score: number;
  amount: string;
  reasons: string[];
  invoices: MatchCandidateInvoice[];
}

export function useMatchCandidates(transactionId: string | null) {
  return useQuery({
    queryKey: [BANK_KEY, "candidates", transactionId],
    enabled: transactionId !== null,
    queryFn: () => api<MatchCandidate[]>(`/api/bank/transactions/${transactionId}/candidates/`),
  });
}

function useTransactionAction<TBody>(path: (id: string) => string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; body?: TBody }) =>
      api<BankTransaction>(path(input.id), { method: "POST", body: input.body ? JSON.stringify(input.body) : undefined }),
    onSuccess: () => client.invalidateQueries({ queryKey: [BANK_KEY] }),
  });
}

export function useMatchTransaction() {
  return useTransactionAction<{ invoices: string[] }>((id) => `/api/bank/transactions/${id}/match/`);
}

export function useIgnoreTransaction() {
  return useTransactionAction<never>((id) => `/api/bank/transactions/${id}/ignore/`);
}

export interface AutoMatchResult {
  matched: number;
  proposed: number;
}

export function useAutoMatch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (account: string) => api<AutoMatchResult>(`/api/bank/auto-match${buildQuery({ account })}`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: [BANK_KEY] }),
  });
}
