// PROJECT_SPECS §12 role checks mirrored client-side for affordances only; the API is authoritative.
import type { MemberRole } from "@/lib/types";

const CONFIRMING_ROLES: readonly string[] = ["owner", "accountant"];

export function isOwner(role: string | null | undefined): boolean {
  return role === "owner";
}

/** viewer cannot confirm invoices (§12); reviewer may review but not confirm. */
export function canConfirmInvoices(role: string | null | undefined): boolean {
  return role !== null && role !== undefined && CONFIRMING_ROLES.includes(role);
}

export const MEMBER_ROLES: readonly MemberRole[] = ["owner", "accountant", "reviewer", "viewer"];
