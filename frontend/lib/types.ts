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

// ---- Mail (§6) ---------------------------------------------------------------------------------
export type Mailbox = Schemas["Mailbox"];
export type MailProvider = Schemas["ProviderEnum"];
export type ThreadList = Schemas["ThreadList"];
export type ThreadDetail = Schemas["ThreadDetail"];
export type ThreadStatus = Schemas["Status98aEnum"];
export type MailMessage = Schemas["Message"];
export type Draft = Schemas["Draft"];
export type DraftSummary = Schemas["DraftSummary"];
export type DraftStatus = Schemas["Status485Enum"];
export type Intent = Schemas["IntentEnum"];
export type Priority = Schemas["PriorityEnum"];
export type StyleGuide = Schemas["StyleGuide"];
export type ReplyTemplate = Schemas["Template"];

// ---- Forecasting (§8) --------------------------------------------------------------------------
export type ForecastRun = Schemas["ForecastRun"];
export type ForecastPoint = Schemas["ForecastPoint"];
export type Scenario = Schemas["Scenario"];
export type RecurringPattern = Schemas["RecurringPattern"];
export type FixedLine = Schemas["FixedLine"];
export type FixedLineCadence = Schemas["FixedLineCadenceEnum"];
export type FixedLineDirection = Schemas["FixedLineDirectionEnum"];
export type ReportSchedule = Schemas["ReportSchedule"];
export type ReportScheduleCadence = Schemas["ReportScheduleCadenceEnum"];
export type ReportFormat = Schemas["FormatEnum"];

// ---- Reconciliation (§3.8 / §11) ----------------------------------------------------------------
export type ReconBatch = Schemas["Batch"];
export type ReconRecord = Schemas["Record"];
export type ReconMatch = Schemas["Match"];
export type MatchType = Schemas["MatchTypeEnum"];
export type ImsAction = Schemas["ImsActionEnum"];
