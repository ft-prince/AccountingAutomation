"""~14 months of realistic demo data for one org. PROJECT_SPECS Phase 9.
Deterministic (seeded). Idempotent: refuses to run twice on the same org unless --reset."""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import GSTINProfile, Organization, OrgMembership, Role, User
from apps.core.audit import AuditEvent
from apps.gst.domain.gstin import compute_checksum
from apps.gst.domain.periods import fy_for_date
from apps.gst.domain.supply import SupplyType
from apps.gst.domain.tax import compute_invoice_totals, compute_line
from apps.invoices.models import Invoice, InvoiceLine, InvoiceStatus, ValidationIssue
from apps.parties.models import ExpenseCategory, Party
from apps.payments.models import BankAccount, BankTransaction, Payment
from apps.payments.services.allocation import allocate, refresh_overdue

D = Decimal
OUR_GSTIN_PREFIX = "27AAGFF2194N1Z"

# (name, kind, state, behaviour, monthly_volume, ticket) — behaviours per Phase 9 prompt
CUSTOMERS = [
    ("Tata Steel Digital", "prompt", "27", 3, D("450000")),
    ("Reliance Industrial IoT", "prompt", "24", 3, D("380000")),
    ("Mahindra Automation", "late15", "27", 2, D("260000")),
    ("Adani Ports Systems", "late15", "24", 2, D("320000")),
    ("JSW Smart Plants", "erratic", "27", 2, D("180000")),
    ("Hindalco Sensors", "erratic", "27", 2, D("120000")),
    ("Bharat Forge Analytics", "prompt", "27", 2, D("95000")),
    ("Larsen Process Control", "late15", "27", 2, D("210000")),
    ("Vedanta Edge Compute", "nonpayer", "29", 1, D("140000")),
    ("Siemens India Partner", "prompt", "29", 2, D("500000")),
    ("Godrej Factory Cloud", "erratic", "27", 1, D("75000")),
    ("Ashok Leyland Telemetry", "late15", "33", 2, D("160000")),
]
VENDORS = [
    ("Prime Workspace Rent LLP", "rent", "27", D("85000"), "Rent"),
    ("Amazon Web Services India", "saas", "29", D("62000"), "Software & SaaS"),
    ("Google Cloud India", "saas", "29", D("28000"), "Software & SaaS"),
    ("Atlassian India", "saas", "27", D("9500"), "Software & SaaS"),
    ("Zoho Corporation", "saas", "33", D("4200"), "Software & SaaS"),
    ("Adani Electricity", "utility", "27", D("18000"), "Utilities"),
    ("Jio Fiber Business", "utility", "27", D("6500"), "Utilities"),
    ("Robu Electronics", "adhoc", "27", D("45000"), "Hardware & Equipment"),
    ("Element14 India", "adhoc", "29", D("70000"), "Hardware & Equipment"),
    ("Blue Dart Express", "adhoc", "27", D("8000"), "Freight & Logistics"),
    ("Deloitte Haskins", "adhoc", "27", D("60000"), "Professional Services"),
    ("MakeMyTrip Business", "adhoc", "06", D("22000"), "Travel"),
    ("Swiggy Corporate", "adhoc", "27", D("3500"), "Meals & Entertainment"),
    ("Amazon Business", "adhoc", "27", D("12000"), "Office Supplies"),
    ("HDFC Ergo", "yearly", "27", D("48000"), "Insurance"),
    ("Freelance Devs Collective", "adhoc", "27", D("90000"), "Salaries & Contractors"),
    ("Kotak Bank Charges", "utility", "27", D("1200"), "Bank Charges"),
    ("Upwork Contractors", "adhoc", "99", D("55000"), "Salaries & Contractors"),
]


def _gstin(state: str, rng: random.Random) -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    pan = (
        "".join(rng.choice(letters) for _ in range(5))
        + f"{rng.randint(1000, 9999)}"
        + rng.choice(letters)
    )
    base = f"{state}{pan}1Z"
    return base + compute_checksum(base)


def _days_to_pay(behaviour: str, rng: random.Random) -> int | None:
    if behaviour == "prompt":
        return rng.randint(-5, 5)
    if behaviour == "late15":
        return rng.randint(10, 22)
    if behaviour == "erratic":
        return rng.choice([rng.randint(-3, 3), rng.randint(20, 45), rng.randint(50, 95)])
    return None  # nonpayer


class Command(BaseCommand):
    help = "Generate ~14 months of demo data (org 'Nexren Demo', user demo@nexren.ai / demo1234)."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--today", type=str, default=None)

    @transaction.atomic
    def handle(self, *args, **opts) -> None:  # type: ignore[no-untyped-def]
        rng = random.Random(opts["seed"])
        today = date.fromisoformat(opts["today"]) if opts["today"] else date.today()
        org, created = Organization.objects.get_or_create(
            name="Nexren Demo",
            defaults={"legal_name": "Nexren AI Private Limited", "pan": "AAGFF2194N"},
        )
        if not created and not opts["reset"]:
            self.stdout.write("Demo org exists; use --reset to regenerate.")
            return
        if not created:
            Invoice.objects.filter(org=org).delete()
            Payment.objects.filter(org=org).delete()
            BankAccount.objects.filter(org=org).delete()
            Party.objects.filter(org=org).delete()
            AuditEvent.objects.filter(org=org)._raw_delete(
                AuditEvent.objects.db
            )  # append-only guard bypass: demo reset only
        call_command("seed_categories", stdout=self.stdout)
        user, _ = User.objects.get_or_create(
            email="demo@nexren.ai", defaults={"full_name": "Demo Owner"}
        )
        user.set_password("demo1234")
        user.save()
        OrgMembership.objects.get_or_create(org=org, user=user, defaults={"role": Role.OWNER})
        our = OUR_GSTIN_PREFIX + compute_checksum(OUR_GSTIN_PREFIX)
        profile, _ = GSTINProfile.objects.get_or_create(
            gstin=our,
            defaults={
                "org": org,
                "state_code": "27",
                "is_default": True,
                "trade_name": "Nexren AI",
            },
        )
        cats = {c.name: c for c in ExpenseCategory.objects.filter(org__isnull=True)}

        start = date(today.year - 1, today.month, 1) - timedelta(days=60)
        months = []
        m = date(start.year, start.month, 1)
        while m <= today:
            months.append(m)
            m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)

        customers = [
            (
                Party.objects.create(
                    org=org,
                    kind="customer",
                    legal_name=n,
                    gstin=_gstin(st, rng),
                    state_code=st,
                    payment_terms_days=30,
                    credit_limit=t * 4,
                    email_domains=[n.split()[0].lower() + ".com"],
                ),
                b,
                v,
                t,
            )
            for n, b, st, v, t in CUSTOMERS
        ]
        vendors = [
            (
                Party.objects.create(
                    org=org,
                    kind="vendor",
                    legal_name=n,
                    gstin=_gstin(st, rng) if st != "99" else None,
                    state_code=st,
                    default_category=cats[c],
                    payment_terms_days=15,
                ),
                k,
                t,
                c,
            )
            for n, k, st, t, c in VENDORS
        ]

        acct = BankAccount.objects.create(
            org=org,
            name="HDFC Current",
            bank="HDFC",
            masked_account="XXXX4321",
            opening_balance=D("1850000"),
            opening_balance_date=start,
        )
        seq = {"out": 0}
        txns: list[tuple[date, Decimal, str, str]] = []
        n_invoices = 0

        def make_invoice(
            party: Party,
            direction: str,
            d: date,
            lines_spec: list[tuple[str, str, Decimal, str]],
            number: str,
            status: str = InvoiceStatus.CONFIRMED,
            irn: bool = True,
            category=None,
        ):  # type: ignore[no-untyped-def]
            nonlocal n_invoices
            supplier_state = "27" if direction == "outward" else party.state_code
            pos = party.state_code if direction == "outward" else "27"
            if party.state_code == "99":
                st = SupplyType.IMPORT
            else:
                st = SupplyType.INTRA if supplier_state == pos else SupplyType.INTER
            computed = [
                compute_line(unit, D("1"), D("0"), D(rate), D("0"), st)
                for _, _, unit, rate in lines_spec
            ]
            totals = compute_invoice_totals(computed)
            inv = Invoice.objects.create(
                org=org,
                gstin_profile=profile,
                party=party,
                direction=direction,
                invoice_number=number,
                invoice_date=d,
                due_date=d + timedelta(days=party.payment_terms_days),
                place_of_supply_state_code=pos,
                supply_type=st.value.lower(),
                irn=f"IRN{rng.getrandbits(64):016x}" if irn and direction == "outward" else "",
                has_qr=irn,
                taxable_value=totals.taxable,
                cgst=totals.cgst,
                sgst=totals.sgst,
                igst=totals.igst,
                cess=totals.cess,
                round_off=totals.round_off,
                total=totals.total,
                status=status,
                confidence=D("0.97")
                if status == InvoiceStatus.CONFIRMED
                else D(str(round(rng.uniform(0.6, 0.9), 3))),
                fy=fy_for_date(d),
                period_month=d.strftime("%Y-%m"),
                itc_eligible=(category.itc_eligible if category else True),
                itc_blocked_reason=""
                if (category is None or category.itc_eligible)
                else f"Section {category.section_17_5_ref}",
                reviewed_at=None,
            )
            InvoiceLine.objects.bulk_create(
                InvoiceLine(
                    invoice=inv,
                    line_no=i + 1,
                    description=desc,
                    hsn_sac=hsn,
                    quantity=1,
                    unit_price=unit,
                    taxable_value=lt.taxable,
                    rate=D(rate),
                    cgst=lt.cgst,
                    sgst=lt.sgst,
                    igst=lt.igst,
                    cess=lt.cess,
                    line_total=lt.line_total,
                    category=category,
                )
                for i, ((desc, hsn, unit, rate), lt) in enumerate(
                    zip(lines_spec, computed, strict=True)
                )
            )
            n_invoices += 1
            return inv

        # --- outward (sales) with payments consistent with behaviour
        for party, behaviour, volume, ticket in customers:
            for m in months:
                for _k in range(volume):
                    d = m + timedelta(days=rng.randint(1, 26))
                    if d > today:
                        continue
                    seq["out"] += 1
                    amount = (ticket * D(str(round(rng.uniform(0.7, 1.3), 2)))).quantize(D("1"))
                    inv = make_invoice(
                        party,
                        "outward",
                        d,
                        [("Industrial AI platform subscription", "998314", amount, "18")],
                        f"NX/{fy_for_date(d)[2:]}/{seq['out']:04d}",
                    )
                    dtp = _days_to_pay(behaviour, rng)
                    if dtp is None:
                        if rng.random() < 0.15:
                            dtp = rng.randint(120, 200)  # the non-payer occasionally pays very late
                        else:
                            continue
                    pay_date = inv.due_date + timedelta(days=dtp)
                    if pay_date <= today:
                        p = Payment.objects.create(
                            org=org,
                            party=party,
                            direction="received",
                            amount=inv.total,
                            date=pay_date,
                            method="neft",
                            reference=f"UTR{rng.getrandbits(40):010x}".upper(),
                        )
                        allocate(p, [(inv, inv.total)], actor=None)
                        txns.append(
                            (
                                pay_date,
                                inv.total,
                                f"NEFT CR-{party.legal_name.upper()}-{p.reference}",
                                p.reference,
                            )
                        )

        # --- inward (purchases): recurring vendors + ad hoc, paid at ~terms
        vi = 0
        for party, kind, ticket, catname in vendors:
            cat = cats[catname]
            for mi, m in enumerate(months):
                occurrences = (
                    1
                    if kind in ("rent", "saas", "utility")
                    else (
                        1
                        if kind == "yearly" and m.month == 4
                        else (1 if kind == "adhoc" and rng.random() < 0.45 else 0)
                    )
                )
                for _ in range(occurrences):
                    d = m + timedelta(days=(3 if kind == "rent" else rng.randint(1, 27)))
                    if d > today:
                        continue
                    vi += 1
                    jitter = D(
                        str(
                            round(
                                rng.uniform(0.98, 1.02)
                                if kind in ("rent", "saas", "utility")
                                else rng.uniform(0.5, 1.6),
                                2,
                            )
                        )
                    )
                    amount = (ticket * jitter).quantize(D("1"))
                    # deliberate 4× SaaS anomaly + a duplicate pair for Phase 17 detectors
                    if (
                        kind == "saas"
                        and party.legal_name.startswith("Google")
                        and mi == len(months) - 2
                    ):
                        amount = amount * 4
                    rate = "18" if catname != "Bank Charges" else "18"
                    inv = make_invoice(
                        party,
                        "inward",
                        d,
                        [
                            (
                                f"{catname} — {m.strftime('%b %Y')}",
                                "998315"
                                if kind == "saas"
                                else "997212"
                                if kind == "rent"
                                else "8543",
                                amount,
                                rate,
                            )
                        ],
                        f"{party.legal_name[:3].upper()}-{vi:05d}",
                        category=cat,
                        irn=False,
                    )
                    if party.legal_name == "Robu Electronics" and mi == len(months) - 3:
                        make_invoice(
                            party,
                            "inward",
                            d + timedelta(days=2),
                            [("Duplicate sensor batch", "8543", amount, rate)],
                            f"{party.legal_name[:3].upper()}-{vi:05d}-DUP",
                            category=cat,
                            irn=False,
                        )
                    pay_date = inv.due_date + timedelta(days=rng.randint(-2, 6))
                    if pay_date <= today:
                        p = Payment.objects.create(
                            org=org,
                            party=party,
                            direction="made",
                            amount=inv.total,
                            date=pay_date,
                            method="neft",
                            reference=f"UTR{rng.getrandbits(40):010x}".upper(),
                        )
                        allocate(p, [(inv, inv.total)], actor=None)
                        txns.append(
                            (
                                pay_date,
                                -inv.total,
                                f"NEFT DR-{party.legal_name.upper()}",
                                p.reference,
                            )
                        )

        # --- deliberately broken / pending invoices
        broken_party = vendors[7][0]
        for i in range(12):
            d = today - timedelta(days=rng.randint(1, 40))
            inv = make_invoice(
                broken_party,
                "inward",
                d,
                [("Unreviewed sensor order", "8543", D(str(rng.randint(5000, 60000))), "18")],
                f"PEND-{i:03d}",
                status=InvoiceStatus.NEEDS_REVIEW,
                category=cats["Hardware & Equipment"],
                irn=False,
            )
            if i % 3 == 0:
                ValidationIssue.objects.create(
                    invoice=inv,
                    code="ARITHMETIC_MISMATCH",
                    severity="warning",
                    field="stated_total",
                    message="Stated total differs from computed by ₹18.00",
                )
            if i % 4 == 0:
                ValidationIssue.objects.create(
                    invoice=inv,
                    code="MISSING_FIELD",
                    severity="error",
                    field="recipient_gstin",
                    message="Recipient GSTIN missing",
                )
        # a duplicate-numbered sale
        dup_src = (
            Invoice.objects.filter(org=org, direction="outward").order_by("-invoice_date").first()
        )
        if dup_src:
            Invoice.objects.create(
                org=org,
                gstin_profile=profile,
                party=dup_src.party,
                direction="outward",
                invoice_number=dup_src.invoice_number,
                invoice_date=dup_src.invoice_date,
                due_date=dup_src.due_date,
                supply_type=dup_src.supply_type,
                taxable_value=dup_src.taxable_value,
                cgst=dup_src.cgst,
                sgst=dup_src.sgst,
                igst=dup_src.igst,
                total=dup_src.total,
                status=InvoiceStatus.DUPLICATE,
                duplicate_of=dup_src,
                fy=dup_src.fy,
                period_month=dup_src.period_month,
                confidence=D("0.93"),
            )

        # --- bank statement: matched history + a tail of unmatched rows + charges
        txns.sort(key=lambda t: t[0])
        bal = acct.opening_balance
        import hashlib

        rows = []
        for d, amt, desc, ref in txns:
            bal += amt
            key = f"{acct.pk}|{d.isoformat()}|{amt}|{desc}|{ref}"
            rows.append(
                BankTransaction(
                    bank_account=acct,
                    date=d,
                    amount=amt,
                    description=desc,
                    reference=ref,
                    balance_after=bal,
                    sha256=hashlib.sha256(key.encode()).hexdigest(),
                    match_status="manual",
                )
            )
        for i in range(8):
            d = today - timedelta(days=rng.randint(0, 20))
            amt = D(str(rng.choice([-590, -1180, 15000, 47200, -2360])))
            bal += amt
            key = f"{acct.pk}|{d.isoformat()}|{amt}|misc{i}"
            rows.append(
                BankTransaction(
                    bank_account=acct,
                    date=d,
                    amount=amt,
                    description=rng.choice(
                        ["UPI-MISC", "NEFT CR-UNKNOWN", "BANK CHARGES", "ATM WDL"]
                    ),
                    reference=f"M{i}",
                    balance_after=bal,
                    sha256=hashlib.sha256(key.encode()).hexdigest(),
                )
            )
        BankTransaction.objects.bulk_create(rows)
        refresh_overdue(org.pk)
        n_pay = Payment.objects.filter(org=org).count()
        self.stdout.write(
            f"generate_demo_data: org={org.pk} invoices={n_invoices} payments={n_pay} "
            f"bank_rows={len(rows)} months={len(months)}"
        )
