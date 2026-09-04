"""Reports. PROJECT_SPECS §7.1: confirmed only, pending count on every response, FY/period stated,
accrual | cash basis, all aggregation in the DB. No Python loops over querysets."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import (
    Case,
    Count,
    DateField,
    DecimalField,
    ExpressionWrapper,
    F,
    Func,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, TruncMonth

from apps.gst.domain.periods import (
    due_date_gstr1,
    due_date_gstr3b,
    fy_bounds,
    fy_for_date,
    itc_deadline,
)
from apps.invoices.models import Invoice, InvoiceLine, InvoiceStatus, PaymentStatus
from apps.payments.models import (
    BankAccount,
    BankBalanceSnapshot,
    BankTransaction,
    MatchStatus,
    PaymentAllocation,
)

ZERO = Decimal("0")
MONEY = DecimalField(max_digits=14, decimal_places=2)


def _sum(field: Any) -> Any:
    return Coalesce(Sum(field), Value(ZERO), output_field=MONEY)


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    basis: str  # accrual | cash

    @property
    def fy(self) -> str:
        return fy_for_date(self.end)

    def meta(self, org: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        confirmed = Invoice.objects.for_org(org).filter(status=InvoiceStatus.CONFIRMED)
        pending = Invoice.objects.for_org(org).filter(status=InvoiceStatus.NEEDS_REVIEW)
        in_period = Q(invoice_date__gte=self.start, invoice_date__lte=self.end)
        return {
            "fy": self.fy,
            "period": {"from": self.start.isoformat(), "to": self.end.isoformat()},
            "basis": self.basis,
            "invoice_count": confirmed.filter(in_period).count(),
            "pending_count": pending.filter(in_period).count(),
            **(extra or {}),
        }


def period_from_params(p: dict[str, str], today: date | None = None) -> Period:
    today = today or date.today()
    basis = p.get("basis", "accrual")
    if basis not in ("accrual", "cash"):
        raise ValueError("basis must be accrual or cash")
    if fy := p.get("fy"):
        start, end = fy_bounds(fy)
    else:
        start, end = fy_bounds(fy_for_date(today))
    if v := p.get("from"):
        start = date.fromisoformat(v)
    if v := p.get("to"):
        end = date.fromisoformat(v)
    if start > end:
        raise ValueError("from must be on or before to")
    return Period(start, end, basis)


def _confirmed(org: Any) -> Any:
    return Invoice.objects.for_org(org).filter(status=InvoiceStatus.CONFIRMED)


def _basis_rows(org: Any, period: Period, direction: str) -> Any:
    """Accrual: invoices by invoice_date. Cash: allocations by payment date."""
    if period.basis == "accrual":
        return (
            _confirmed(org)
            .filter(direction=direction, invoice_date__range=(period.start, period.end))
            .annotate(basis_amount=F("taxable_value"), month=TruncMonth("invoice_date"))
        )
    return PaymentAllocation.objects.filter(
        invoice__org=org,
        invoice__status=InvoiceStatus.CONFIRMED,
        invoice__direction=direction,
        payment__date__range=(period.start, period.end),
    ).annotate(
        # scale allocation to its taxable share: amount × taxable/total
        basis_amount=ExpressionWrapper(
            F("amount")
            * F("invoice__taxable_value")
            / Case(When(invoice__total=0, then=Value(Decimal("1"))), default=F("invoice__total")),
            output_field=MONEY,
        ),
        month=TruncMonth("payment__date"),
        party=F("invoice__party"),
    )


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def summary(org: Any, period: Period) -> dict[str, Any]:
    rev = _q(_basis_rows(org, period, "outward").aggregate(v=_sum("basis_amount"))["v"])
    exp = _q(_basis_rows(org, period, "inward").aggregate(v=_sum("basis_amount"))["v"])
    cogs = _cogs(org, period)
    tax = tax_liability(org, period)
    gross = rev - cogs
    return {
        "revenue": str(rev),
        "expenses": str(exp),
        "cogs": str(cogs),
        "gross_margin": str(gross),
        "gross_margin_pct": str((gross / rev * 100).quantize(Decimal("0.1"))) if rev else None,
        "net": str(rev - exp),
        "tax_payable": tax["totals"]["net_payable"],
        "pending_value": str(
            Invoice.objects.for_org(org)
            .filter(
                status=InvoiceStatus.NEEDS_REVIEW, invoice_date__range=(period.start, period.end)
            )
            .aggregate(v=_sum("total"))["v"]
        ),
        "meta": period.meta(org),
    }


COGS_CATEGORIES = ("Hardware & Equipment", "Freight & Logistics", "Salaries & Contractors")


def _cogs(org: Any, period: Period) -> Decimal:
    if period.basis != "accrual":
        return ZERO  # cash-basis COGS is not split by category in v1
    return InvoiceLine.objects.filter(
        invoice__org=org,
        invoice__status=InvoiceStatus.CONFIRMED,
        invoice__direction="inward",
        invoice__invoice_date__range=(period.start, period.end),
        category__name__in=COGS_CATEGORIES,
    ).aggregate(v=_sum("taxable_value"))["v"]


def pnl(org: Any, period: Period) -> dict[str, Any]:
    rev = {
        r["month"]: _q(r["v"])
        for r in _basis_rows(org, period, "outward")
        .values("month")
        .annotate(v=_sum("basis_amount"))
        .order_by("month")
    }
    exp = {
        r["month"]: _q(r["v"])
        for r in _basis_rows(org, period, "inward")
        .values("month")
        .annotate(v=_sum("basis_amount"))
        .order_by("month")
    }
    cogs: dict[date, Decimal] = {}
    if period.basis == "accrual":
        cogs = {
            r["m"]: r["v"]
            for r in InvoiceLine.objects.filter(
                invoice__org=org,
                invoice__status=InvoiceStatus.CONFIRMED,
                invoice__direction="inward",
                invoice__invoice_date__range=(period.start, period.end),
                category__name__in=COGS_CATEGORIES,
            )
            .annotate(m=TruncMonth("invoice__invoice_date"))
            .values("m")
            .annotate(v=_sum("taxable_value"))
        }
    months = sorted(set(rev) | set(exp))
    rows = []
    for m in months:
        r, e, c = rev.get(m, ZERO), exp.get(m, ZERO), cogs.get(m, ZERO)
        rows.append(
            {
                "month": m.strftime("%Y-%m"),
                "revenue": str(r),
                "cogs": str(c),
                "opex": str(e - c),
                "net": str(r - e),
            }
        )
    return {"rows": rows, "meta": period.meta(org)}


def categories(org: Any, period: Period) -> dict[str, Any]:
    base = InvoiceLine.objects.filter(
        invoice__org=org, invoice__status=InvoiceStatus.CONFIRMED, invoice__direction="inward"
    )
    cur = (
        base.filter(invoice__invoice_date__range=(period.start, period.end))
        .values(name=Coalesce("category__name", Value("Uncategorised")))
        .annotate(v=_sum("taxable_value"), n=Count("id"))
        .order_by("-v")
    )
    span = (period.end - period.start).days + 1
    prev_start, prev_end = period.start - timedelta(days=span), period.start - timedelta(days=1)
    prev = {
        r["name"]: r["v"]
        for r in base.filter(invoice__invoice_date__range=(prev_start, prev_end))
        .values(name=Coalesce("category__name", Value("Uncategorised")))
        .annotate(v=_sum("taxable_value"))
    }
    rows = [
        {
            "category": r["name"],
            "amount": str(r["v"]),
            "invoice_lines": r["n"],
            "previous": str(prev.get(r["name"], ZERO)),
            "delta": str(r["v"] - prev.get(r["name"], ZERO)),
        }
        for r in cur
    ]
    movers = sorted(rows, key=lambda x: abs(Decimal(x["delta"])), reverse=True)[:5]
    return {
        "rows": rows,
        "top_movers": movers,
        "previous_period": {"from": prev_start.isoformat(), "to": prev_end.isoformat()},
        "meta": period.meta(org),
    }


def parties(org: Any, period: Period, limit: int = 10) -> dict[str, Any]:
    def top(direction: str) -> tuple[list[dict[str, Any]], Decimal]:
        rows = list(
            _basis_rows(org, period, direction)
            .values(pid=F("party"), name=F("party__legal_name"))
            .annotate(v=_sum("basis_amount"))
            .order_by("-v")
        )
        total = sum((r["v"] for r in rows), ZERO)
        return [
            {
                "party": str(r["pid"]),
                "name": r["name"],
                "amount": str(r["v"]),
                "share_pct": str((r["v"] / total * 100).quantize(Decimal("0.1"))) if total else "0",
            }
            for r in rows[:limit]
        ], total

    customers, rev_total = top("outward")
    vendors, exp_total = top("inward")
    shares = [Decimal(c["share_pct"]) for c in customers]
    return {
        "top_customers": customers,
        "top_vendors": vendors,
        "concentration": {
            "top1_pct": str(shares[0]) if shares else "0",
            "top3_pct": str(sum(shares[:3])) if shares else "0",
        },
        "meta": period.meta(org, {"revenue_total": str(rev_total), "spend_total": str(exp_total)}),
    }


BUCKETS = (("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, None))


def _aging(org: Any, direction: str, as_of: date) -> dict[str, Any]:
    open_q = (
        _confirmed(org)
        .filter(direction=direction)
        .exclude(payment_status__in=[PaymentStatus.PAID, PaymentStatus.WRITTEN_OFF])
        .filter(total__gt=F("amount_paid"))
    )
    outstanding = ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY)
    anchor = Coalesce("due_date", "invoice_date")
    # Postgres: date - date = integer days, so bucketing happens in SQL.
    age = Func(
        Value(as_of, output_field=DateField()),
        anchor,
        template="(%(expressions)s)",
        arg_joiner=" - ",
        output_field=IntegerField(),
    )
    rows = open_q.annotate(age=age).annotate(
        bucket=Case(
            *[
                When(
                    **({"age__gte": lo} if hi is None else {"age__gte": lo, "age__lte": hi}),
                    then=Value(label),
                )
                for label, lo, hi in BUCKETS
            ],
            default=Value("0-30"),
        ),
        outstanding=outstanding,
    )
    per_party = (
        rows.values(pid=F("party"), name=F("party__legal_name"), b=F("bucket"))
        .annotate(v=_sum("outstanding"))
        .order_by("name")
    )
    table: dict[str, dict[str, Any]] = {}
    for r in per_party:
        row = table.setdefault(
            str(r["pid"]),
            {
                "party": str(r["pid"]),
                "name": r["name"],
                **{b[0]: "0" for b in BUCKETS},
                "total": ZERO,
            },
        )
        row[r["b"]] = str(r["v"])
        row["total"] += r["v"]
    by_bucket = {
        r["bucket"]: (r["v"], r["n"])
        for r in rows.values("bucket").annotate(v=_sum("outstanding"), n=Count("id"))
    }
    totals = {b[0]: str(by_bucket.get(b[0], (ZERO, 0))[0]) for b in BUCKETS}
    grand = sum((v for v, _ in by_bucket.values()), ZERO)
    open_count = sum(n for _, n in by_bucket.values())
    out_rows = sorted(
        ({**r, "total": str(r["total"])} for r in table.values()),
        key=lambda r: Decimal(r["total"]),
        reverse=True,
    )
    return {
        "rows": out_rows,
        "totals": {**totals, "total": str(grand)},
        "as_of": as_of.isoformat(),
        "open_invoices": open_count,
    }


def _as_of(period: Period, as_of: date | None) -> date:
    """Aging is always 'as of' a real day: the period end, but never the future."""
    return as_of or min(period.end, date.today())


def ar_aging(org: Any, period: Period, as_of: date | None = None) -> dict[str, Any]:
    return {**_aging(org, "outward", _as_of(period, as_of)), "meta": period.meta(org)}


def ap_aging(org: Any, period: Period, as_of: date | None = None) -> dict[str, Any]:
    return {**_aging(org, "inward", _as_of(period, as_of)), "meta": period.meta(org)}


def dso_dpo(org: Any, period: Period, as_of: date | None = None) -> dict[str, Any]:
    """Trailing 90 days: DSO = AR / (sales/90); DPO = AP / (purchases/90)."""
    as_of = _as_of(period, as_of)
    start = as_of - timedelta(days=89)
    win = _confirmed(org).filter(invoice_date__range=(start, as_of))
    sales = win.filter(direction="outward").aggregate(v=_sum("total"))["v"]
    purchases = win.filter(direction="inward").aggregate(v=_sum("total"))["v"]
    open_q = _confirmed(org).exclude(
        payment_status__in=[PaymentStatus.PAID, PaymentStatus.WRITTEN_OFF]
    )
    ar = (
        open_q.filter(direction="outward")
        .annotate(o=ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY))
        .aggregate(v=_sum("o"))["v"]
    )
    ap = (
        open_q.filter(direction="inward")
        .annotate(o=ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY))
        .aggregate(v=_sum("o"))["v"]
    )
    dso = (ar / (sales / 90)).quantize(Decimal("0.1")) if sales else None
    dpo = (ap / (purchases / 90)).quantize(Decimal("0.1")) if purchases else None
    return {
        "dso_days": str(dso) if dso is not None else None,
        "dpo_days": str(dpo) if dpo is not None else None,
        "receivables": str(ar),
        "payables": str(ap),
        "sales_90d": str(sales),
        "purchases_90d": str(purchases),
        "window": {"from": start.isoformat(), "to": as_of.isoformat()},
        "meta": period.meta(org),
    }


def tax_liability(org: Any, period: Period, today: date | None = None) -> dict[str, Any]:
    """Per return period: output tax, eligible/blocked ITC, RCM, net payable, due dates."""
    today = today or date.today()
    inv = _confirmed(org).filter(invoice_date__range=(period.start, period.end))
    tax_expr = F("cgst") + F("sgst") + F("igst") + F("cess")
    rows = (
        inv.values("period_month")
        .annotate(
            output_tax=_sum(
                Case(
                    When(direction="outward", then=tax_expr),
                    default=Value(ZERO),
                    output_field=MONEY,
                )
            ),
            eligible_itc=_sum(
                Case(
                    When(
                        direction="inward",
                        itc_eligible=True,
                        is_reverse_charge=False,
                        then=tax_expr,
                    ),
                    default=Value(ZERO),
                    output_field=MONEY,
                )
            ),
            blocked_itc=_sum(
                Case(
                    When(direction="inward", itc_eligible=False, then=tax_expr),
                    default=Value(ZERO),
                    output_field=MONEY,
                )
            ),
            rcm=_sum(
                Case(
                    When(direction="inward", is_reverse_charge=True, then=tax_expr),
                    default=Value(ZERO),
                    output_field=MONEY,
                )
            ),
            n=Count("id"),
        )
        .order_by("period_month")
    )
    out = []
    totals = {
        "output_tax": ZERO,
        "eligible_itc": ZERO,
        "blocked_itc": ZERO,
        "rcm": ZERO,
        "net_payable": ZERO,
    }
    for r in rows:
        y, m = r["period_month"].split("-")
        rp = f"{m}{y}"
        # §3.6: RCM is paid in cash (3.1(d)) and claimed back (4(A)(3)): net 0, shown.
        net = r["output_tax"] - r["eligible_itc"]
        first = date(int(y), int(m), 1)
        row = {
            "period": r["period_month"],
            "return_period": rp,
            "output_tax": str(r["output_tax"]),
            "eligible_itc": str(r["eligible_itc"]),
            "blocked_itc": str(r["blocked_itc"]),
            "rcm": str(r["rcm"]),
            "net_payable": str(net),
            "invoices": r["n"],
            "gstr1_due": due_date_gstr1(rp, False).isoformat(),
            "gstr3b_due": due_date_gstr3b(rp, False, 1).isoformat(),
            "itc_deadline": itc_deadline(fy_for_date(first)).isoformat(),
        }
        out.append(row)
        for k in ("output_tax", "eligible_itc", "blocked_itc", "rcm"):
            totals[k] += r[k]
        totals["net_payable"] += net
    upcoming = [
        {
            "return": "GSTR-3B",
            "period": r["period"],
            "due": r["gstr3b_due"],
            "amount": r["net_payable"],
        }
        for r in out
        if date.fromisoformat(r["gstr3b_due"]) >= today
    ]
    upcoming += [
        {
            "return": "GSTR-1",
            "period": r["period"],
            "due": r["gstr1_due"],
            "amount": r["output_tax"],
        }
        for r in out
        if date.fromisoformat(r["gstr1_due"]) >= today
    ]
    upcoming.sort(key=lambda u: u["due"])
    return {
        "rows": out,
        "totals": {k: str(v) for k, v in totals.items()},
        "upcoming": upcoming[:6],
        "meta": period.meta(org),
    }


def itc_at_risk(org: Any, period: Period, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    inward = _confirmed(org).filter(
        direction="inward", invoice_date__range=(period.start, period.end)
    )
    tax_expr = ExpressionWrapper(F("cgst") + F("sgst") + F("igst") + F("cess"), output_field=MONEY)
    missing_irn = inward.filter(
        irn="", party__aato_bracket__in=["5_to_10cr", "above_10cr"]
    ).annotate(t=tax_expr)
    blocked = inward.filter(itc_eligible=False).annotate(t=tax_expr)
    past_deadline = inward.annotate(t=tax_expr).filter(
        fy__in=[
            fy for fy in inward.values_list("fy", flat=True).distinct() if itc_deadline(fy) < today
        ]
    )
    not_in_2b = (
        inward.filter(irn="", party__aato_bracket="below_5cr").annotate(t=tax_expr).none()
    )  # Phase 13 populates via reconciliation

    def block(qs: Any, reason: str) -> dict[str, Any]:
        return {
            "reason": reason,
            "count": qs.count(),
            "tax_at_risk": str(qs.aggregate(v=_sum("t"))["v"]),
            "invoices": [
                {
                    "id": str(i.pk),
                    "invoice_number": i.invoice_number,
                    "party": i.party.legal_name,
                    "tax": str(i.t),
                }
                for i in qs.select_related("party")[:20]
            ],
        }

    blocks = [
        block(missing_irn, "missing_irn"),
        block(blocked, "blocked_category"),
        block(past_deadline, "past_itc_deadline"),
        block(not_in_2b, "not_in_2b"),
    ]
    return {
        "blocks": blocks,
        "total_at_risk": str(sum((Decimal(b["tax_at_risk"]) for b in blocks), ZERO)),
        "meta": period.meta(org),
    }


def customer_profit(org: Any, period: Period) -> dict[str, Any]:
    """Revenue − costs per customer; costs tagged in Invoice.notes as customer:<party_id>."""
    rev = (
        _basis_rows(org, period, "outward")
        .values(pid=F("party"), name=F("party__legal_name"))
        .annotate(v=_sum("basis_amount"))
        .order_by("-v")
    )
    costs = _confirmed(org).filter(
        direction="inward",
        invoice_date__range=(period.start, period.end),
        notes__contains="customer:",
    )
    cost_by: dict[str, Decimal] = {}
    for c in costs.values_list("notes", "taxable_value"):
        for token in c[0].split():
            if token.startswith("customer:"):
                cost_by[token[9:]] = cost_by.get(token[9:], ZERO) + c[1]
    rows = [
        {
            "party": str(r["pid"]),
            "name": r["name"],
            "revenue": str(r["v"]),
            "attributed_costs": str(cost_by.get(str(r["pid"]), ZERO)),
            "profit": str(r["v"] - cost_by.get(str(r["pid"]), ZERO)),
        }
        for r in rev
    ]
    return {
        "rows": rows,
        "meta": period.meta(org, {"attribution": "Invoice.notes tag customer:<party_id>"}),
    }


def cash_position(org: Any, period: Period) -> dict[str, Any]:
    accounts = []
    total = ZERO
    for acct in BankAccount.objects.for_org(org).filter(is_active=True):
        snap = (
            BankBalanceSnapshot.objects.for_org(org)
            .filter(bank_account=acct)
            .order_by("-date", "-created_at")
            .first()
        )
        latest_txn = (
            BankTransaction.objects.filter(bank_account=acct, balance_after__isnull=False)
            .order_by("-date", "-created_at")
            .first()
        )
        cand = [(s.date, s.balance, "snapshot") for s in [snap] if s] + [
            (t.date, t.balance_after, "statement") for t in [latest_txn] if t
        ]
        if cand:
            d, bal, src = max(cand, key=lambda c: c[0])
        else:
            d, bal, src = acct.opening_balance_date, acct.opening_balance, "opening"
        total += bal or ZERO
        unmatched = BankTransaction.objects.filter(
            bank_account=acct, match_status=MatchStatus.UNMATCHED
        ).aggregate(
            n=Count("id"),
            credits=_sum(
                Case(When(amount__gt=0, then="amount"), default=Value(ZERO), output_field=MONEY)
            ),
            debits=_sum(
                Case(When(amount__lt=0, then="amount"), default=Value(ZERO), output_field=MONEY)
            ),
        )
        accounts.append(
            {
                "account": str(acct.pk),
                "name": acct.name,
                "balance": str(bal or ZERO),
                "as_of": d.isoformat() if d else None,
                "source": src,
                "unmatched": {
                    "count": unmatched["n"],
                    "credits": str(unmatched["credits"]),
                    "debits": str(unmatched["debits"]),
                },
            }
        )
    return {"accounts": accounts, "total_cash": str(total), "meta": period.meta(org)}


REPORTS = {
    "summary": summary,
    "pnl": pnl,
    "categories": categories,
    "parties": parties,
    "ar-aging": ar_aging,
    "ap-aging": ap_aging,
    "dso-dpo": dso_dpo,
    "tax-liability": tax_liability,
    "itc-at-risk": itc_at_risk,
    "customer-profit": customer_profit,
    "cash-position": cash_position,
}
