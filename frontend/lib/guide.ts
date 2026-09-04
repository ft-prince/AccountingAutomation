/** Content for /guide. Pure data: what each module does, when to use it, and which sample
 * file exercises it. Kept out of the page so a test can check every link resolves. */

export interface SampleFile {
  /** Served statically from frontend/public/samples. */
  file: string;
  label: string;
  /** What this file is designed to demonstrate. */
  demonstrates: string;
  /** Where to upload it. */
  target: string;
}

export interface GuideModule {
  id: string;
  title: string;
  route: string;
  /** One sentence: the outcome, not the mechanism. */
  what: string;
  /** The pipeline, in order. */
  how: readonly string[];
  /** When a finance person reaches for it. */
  when: string;
  /** Click-by-click, so the reader can reproduce it. */
  steps: readonly string[];
  samples: readonly SampleFile[];
  /** Anything that will not work without more setup. */
  caveat?: string;
}

export const DEMO_LOGIN = { email: "demo@nexren.ai", password: "demo1234" } as const;

export const SAMPLE_DIR = "/samples";

export const MODULES: readonly GuideModule[] = [
  {
    id: "invoices",
    title: "Invoices and GST",
    route: "/upload",
    what: "A supplier PDF becomes a GST-validated ledger entry that a human confirms.",
    how: [
      "Upload stores the file and takes its SHA-256, so the same document is never charged for twice.",
      "A background worker sends the PDF to Claude with a strict tool schema in which every number is a string.",
      "The result is parsed to Decimal, then every tax figure is recomputed from taxable value and rate. The extracted figures are only compared, never trusted.",
      "GST rules run: GSTIN checksum, place of supply, rate valid on the invoice date, Rule 46 completeness, arithmetic to the paisa.",
      "The invoice is filed as needs_review with its issues attached. Auto-confirm is a feature flag, off by default, and only the rules can trigger it.",
    ],
    when: "Every purchase bill and sales invoice, as it arrives.",
    steps: [
      "Open Upload and drop the sample PDFs, or drop the zip to test bulk ingest.",
      "Watch each row move from pending to extracted.",
      "Open Review. Invoices are queued lowest-confidence first.",
      "Press ? to see the shortcuts. Edit a line and watch the totals recompute as you type.",
      "Press Enter to confirm and advance. The server's Decimal result is the one that gets stored.",
    ],
    samples: [
      {
        file: "invoice-vendor-intra-18.pdf",
        label: "Vendor bill, intra-state 18%",
        demonstrates: "The clean path. Maharashtra to Maharashtra, so tax splits into CGST and SGST.",
        target: "Upload",
      },
      {
        file: "invoice-vendor-inter-18.pdf",
        label: "Vendor bill, inter-state 18%",
        demonstrates: "Karnataka to Maharashtra, so the whole rate goes to IGST. Never both heads on one line.",
        target: "Upload",
      },
      {
        file: "invoice-broken.pdf",
        label: "Vendor bill with defects",
        demonstrates: "No recipient GSTIN and a total 500 rupees too high. Produces a Rule 46 error and an arithmetic mismatch you must resolve or override.",
        target: "Upload",
      },
      {
        file: "invoice-sales-outward.pdf",
        label: "Sales invoice",
        demonstrates: "We are the supplier, so it files as outward and becomes a receivable.",
        target: "Upload",
      },
      {
        file: "invoices-bulk.zip",
        label: "All five in a zip",
        demonstrates: "Bulk ingest. The zip is expanded server-side and each file is deduplicated separately.",
        target: "Upload",
      },
    ],
    caveat:
      "Extraction calls the Anthropic API. Without ANTHROPIC_API_KEY in .env the upload still succeeds and the run is recorded as failed with the reason.",
  },
  {
    id: "payments",
    title: "Payments and bank matching",
    route: "/bank",
    what: "Bank rows are matched to open invoices, and payment status follows from the allocations.",
    how: [
      "A statement is imported through a per-bank column mapping. Each row is hashed, so re-importing the same statement adds nothing.",
      "Auto-match scores each unmatched row on amount, party name in the narration, UTR or reference found in the invoice notes, and distance from the due date.",
      "It accepts only a single unambiguous high-confidence candidate and proposes the rest. A credit never settles a purchase bill, and a debit never settles a sale.",
      "Allocations drive amount_paid and payment status. Setting those directly is rejected by the model layer.",
    ],
    when: "Whenever a statement arrives, and before any receivables report you intend to trust.",
    steps: [
      "Open Bank and create an account, or use the demo account that already exists.",
      "Import a sample statement. The mapping is detected from the column headers and previewed before import.",
      "Press Auto-match. Confident rows are matched; the rest appear as proposals with their reasons.",
      "In the match queue, use J and K to move and Enter to accept the top candidate.",
      "Open the linked invoice and see its status has become partial or paid.",
    ],
    samples: [
      { file: "bank-statement-hdfc.csv", label: "HDFC export", demonstrates: "Separate withdrawal and deposit columns, DD/MM/YY dates, Indian digit grouping in the amounts.", target: "Bank, Import statement" },
      { file: "bank-statement-icici.csv", label: "ICICI export", demonstrates: "The same data in ICICI's column names, including the rupee suffix in the headers.", target: "Bank, Import statement" },
      { file: "bank-statement-sbi.csv", label: "SBI export", demonstrates: "Textual dates such as 01 Sep 2026, and debit and credit columns.", target: "Bank, Import statement" },
      { file: "bank-statement-generic.csv", label: "Generic export", demonstrates: "A single signed amount column, for any bank without a dedicated mapping.", target: "Bank, Import statement" },
    ],
  },
  {
    id: "reports",
    title: "Reporting",
    route: "/reports",
    what: "Profit and loss, ageing, tax liability and cash position, on an accrual or cash basis.",
    how: [
      "Only confirmed invoices count. Every response also carries the number of invoices still pending review, so a total is never quoted without its denominator.",
      "Aggregation happens in the database, not in Python loops. Each report states its financial year, period and basis.",
      "Tax liability derives GSTR-1 and GSTR-3B due dates from the return period, so upcoming payments appear with amounts attached.",
    ],
    when: "Month end, before a filing, or any time someone asks what the position is.",
    steps: [
      "Open Reports and pick a period. The financial year runs 1 April to 31 March.",
      "Toggle between accrual and cash. Accrual counts invoices by date; cash counts money that actually moved.",
      "Note the pending badge on every report. That is the work still sitting in Review.",
      "Open Tax liability to see output tax, eligible and blocked input credit, and the next due date.",
    ],
    samples: [],
  },
  {
    id: "returns",
    title: "GST returns and 2B reconciliation",
    route: "/reconciliation",
    what: "Export GSTR-1 and GSTR-3B, and compare what your suppliers filed against your own books.",
    how: [
      "GSTR-1 is built from confirmed outward invoices into B2B, B2CL, B2CS, export and HSN summary sections.",
      "GSTR-3B maps outward supplies, reverse charge, and eligible against blocked input credit into the return's tables.",
      "Importing a GSTR-2B download classifies every line as exact, fuzzy, value mismatch, missing in books, or missing in 2B, and totals the input credit at risk.",
      "Each record carries an accept, reject or pend action, which is written to the append-only audit log.",
    ],
    when: "Between the 14th, when 2B is generated, and your filing date.",
    steps: [
      "First upload and confirm the three vendor bills above. The sample 2B is written to line up with them.",
      "Open Reconciliation, choose period 08/2026, and import the sample 2B.",
      "Press Run. You should see one exact match, one fuzzy match on the number format, one value mismatch of 500 rupees, and one line missing from your books.",
      "Accept, reject or pend each record.",
      "Download GSTR-1 and GSTR-3B JSON from Reports, Exports.",
    ],
    samples: [
      {
        file: "gstr2b-082026.json",
        label: "GSTR-2B for August 2026",
        demonstrates: "Four supplier lines designed to produce one of each match type against the sample vendor bills.",
        target: "Reconciliation, Import 2B",
      },
    ],
    caveat:
      "The JSON follows the published GSTN shapes, but loading a real export into the GSTN offline tool is a check only you can run.",
  },
  {
    id: "email",
    title: "Client email assistant",
    route: "/inbox",
    what: "Client email is classified, a reply is drafted with your real financial data, and a human sends it.",
    how: [
      "A connected mailbox syncs every two minutes. Message bodies are sanitised before storage and remote images are never fetched.",
      "Each thread is classified by intent and priority, and resolved to a party by sender address, then domain, then any GSTIN or invoice number in the text.",
      "Drafting pulls context from your own database only, and wraps the inbound message in delimiters marking it as untrusted data.",
      "An independent guardrail pass then checks the draft: every amount, date and invoice number must exist in the snapshot the model was given. Discount promises, bank details, legal language and injection attempts each raise a flag.",
      "Approve is refused while any flag is unacknowledged. Sending happens through exactly one gateway that requires a reviewer, and a test fails the build if the provider send API is called anywhere else.",
    ],
    when: "A shared finance inbox where the same questions arrive daily: where is my invoice, when will you pay, send me a statement.",
    steps: [
      "Open Settings, Mailboxes and connect Gmail or Microsoft. Read access is requested first.",
      "Wait for the sync, then open Inbox and pick a thread.",
      "Read the draft, then the flags above it. Click a flag to acknowledge it.",
      "Edit the text if you want, then approve and send. The difference between the draft and what you sent is recorded.",
    ],
    samples: [],
    caveat:
      "This needs Google or Microsoft OAuth credentials in .env. There is no sample file, because mail arrives over the provider API rather than by upload. Until a mailbox is connected, Inbox shows its empty state.",
  },
  {
    id: "forecast",
    title: "Cashflow forecasting",
    route: "/forecast",
    what: "Thirteen weeks of cash, with an uncertainty band and a runway date.",
    how: [
      "Opening cash comes from the latest bank balance. Receivables and payables come from confirmed invoices.",
      "For each customer, the engine measures how late they actually pay from your own allocation history, and falls back to the org-wide pattern and then to payment terms when there is not enough history.",
      "Recurring expenses are detected from repeated bills of similar amount and spacing. Statutory outflows come from the GSTR-3B estimate on its due date.",
      "Two thousand seeded Monte Carlo paths give the P10, P50 and P90 band. The deterministic path, with everything on its due date, is exact Decimal arithmetic.",
      "A rolling-origin backtest scores past forecasts, and the badge tells you whether the bands are calibrated. Under ninety days of history the bands are hidden entirely.",
    ],
    when: "Weekly, and before any hiring, purchase or credit decision.",
    steps: [
      "Open Forecast. The demo org has fifteen months of history, so a run already exists.",
      "Read the backtest badge first. It currently reports the bands as miscalibrated on demo data, which is the honest result and not a display bug.",
      "Look at the drivers table for the largest movements in the next thirty days.",
      "Create a scenario, such as delaying a large customer by thirty days, and run it to overlay the result.",
      "Confirm or dismiss the detected recurring expenses to sharpen the outflow side.",
    ],
    samples: [],
  },
] as const;

/** Every sample referenced anywhere in the guide, in a flat list for the downloads section. */
export const ALL_SAMPLES: readonly (SampleFile & { module: string })[] = MODULES.flatMap((m) =>
  m.samples.map((s) => ({ ...s, module: m.title })),
);
