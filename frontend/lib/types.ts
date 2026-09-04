// Short aliases onto the generated OpenAPI schema (lib/types.gen.ts). Never hand-write API shapes here;
// regenerate with `npm run gen:types`. Report responses have no schema yet — see lib/reports.ts.
import type { components } from "@/lib/types.gen";

type Schemas = components["schemas"];

export type Document = Schemas["Document"];
export type DocumentStatus = Schemas["DocumentStatusEnum"];
export type InvoiceList = Schemas["InvoiceList"];
export type InvoiceDetail = Schemas["InvoiceDetail"];
export type InvoiceLine = Schemas["Line"];
export type InvoiceIssue = Schemas["Issue"];
export type InvoiceStatus = Schemas["StatusE97Enum"];
export type InvoiceDirection = Schemas["Direction7b9Enum"];
export type PaymentStatus = Schemas["PaymentStatusEnum"];
export type Payment = Schemas["Payment"];
export type PaymentDirection = Schemas["PaymentDirectionEnum"];
export type PaymentMethod = Schemas["MethodEnum"];
export type Allocation = Schemas["Allocation"];
export type BankAccount = Schemas["BankAccount"];
export type BankTransaction = Schemas["Transaction"];
export type MatchStatus = Schemas["MatchStatusEnum"];
export type Party = Schemas["Party"];
export type PartyKind = Schemas["KindEnum"];
export type Category = Schemas["Category"];
export type GstinProfile = Schemas["GSTINProfile"];
export type Membership = Schemas["Membership"];
export type MemberRole = Schemas["RoleEnum"];
export type ApiKey = Schemas["APIKey"];
