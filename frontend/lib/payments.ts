"use client";

import Big from "big.js";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { buildQuery, type Paginated } from "@/lib/query";
import type { InvoiceList, Payment, PaymentDirection, PaymentMethod } from "@/lib/types";

export const PAYMENTS_KEY = "payments";
const OPEN_INVOICES_PAGE_SIZE = 100;
const PAYMENTS_PAGE_SIZE = 100;

export interface PaymentFilters {
  direction?: PaymentDirection | "";
  party?: string;
}

export function usePayments(filters: PaymentFilters = {}) {
  return useQuery({
    queryKey: [PAYMENTS_KEY, "list", filters],
    queryFn: () =>
      api<Paginated<Payment>>(`/api/payments/${buildQuery({ direction: filters.direction, party: filters.party, page_size: PAYMENTS_PAGE_SIZE })}`),
  });
}

/** A payment with money still to allocate. Computed client-side; `?unallocated=1` is filtered server-side once available. */
export function isUnallocated(payment: Payment): boolean {
  return new Big(payment.amount ?? "0").gt(new Big(payment.allocated ?? "0"));
}

export interface NewPayment {
  party: string;
  direction: PaymentDirection;
  amount: string;
  date: string;
  method: PaymentMethod;
  reference: string;
  notes?: string;
}

export function useCreatePayment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewPayment) => api<Payment>("/api/payments/", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: [PAYMENTS_KEY] }),
  });
}

export function useAllocatePayment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { paymentId: string; items: { invoice: string; amount: string }[] }) =>
      api<Payment>(`/api/payments/${input.paymentId}/allocate/`, { method: "POST", body: JSON.stringify({ items: input.items }) }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [PAYMENTS_KEY] });
      void client.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}

/** Confirmed invoices for a party with an outstanding balance, in the direction a payment would settle. */
export function useOpenInvoices(partyId: string, direction: PaymentDirection | "") {
  const invoiceDirection = direction === "received" ? "outward" : direction === "made" ? "inward" : "";
  return useQuery({
    queryKey: ["invoices", "open", partyId, invoiceDirection],
    enabled: partyId !== "" && invoiceDirection !== "",
    queryFn: async () => {
      const page = await api<Paginated<InvoiceList>>(
        `/api/invoices/${buildQuery({ party: partyId, status: "confirmed", direction: invoiceDirection, ordering: "due_date", page_size: OPEN_INVOICES_PAGE_SIZE })}`,
      );
      return page.results.filter((invoice) => new Big(invoice.outstanding).gt(0));
    },
  });
}
