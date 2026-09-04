"""Rolling-origin backtest against the org's own history (PROJECT_SPECS §8.7)."""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Min, Q, Sum

from apps.accounts.models import Organization
from apps.forecasting.domain.backtest import (
    BACKTEST_N_PATHS,
    CHECKPOINT_DAYS,
    BacktestOrigin,
    BacktestResult,
    backtest,
)
from apps.forecasting.services.inputs import (
    MIN_HISTORY_DAYS,
    assemble_inputs,
    invoice_states,
    recurring_vendor_keys,
)
from apps.invoices.models import Invoice, InvoiceStatus
from apps.payments.models import PaymentAllocation, PaymentDirection

ZERO = Decimal("0")


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def month_ends_between(first: date, last: date) -> list[date]:
    out: list[date] = []
    current = month_end(first)
    while current <= last:
        out.append(current)
        current = month_end(current + timedelta(days=1))
    return out


def actual_net_flow(
    org: Organization, origin: date, end_inclusive: date, recurring_vendors: set[str]
) -> Decimal:
    """Allocated payments in (origin, end], restricted to what the engine claims to forecast
    (§8.3): receipts against invoices known at the origin, minus payments against invoices
    known at the origin or billed by a vendor with a recurring pattern at the origin.
    Un-invoiced revenue and ad hoc spend are outside the model, so they are outside the
    score; the params record this basis."""
    window = PaymentAllocation.objects.filter(
        invoice__org=org, payment__date__gt=origin, payment__date__lte=end_inclusive
    )
    received = window.filter(
        payment__direction=PaymentDirection.RECEIVED, invoice__invoice_date__lte=origin
    ).aggregate(total=Sum("amount"))["total"]
    made = window.filter(
        Q(invoice__invoice_date__lte=origin) | Q(invoice__party_id__in=recurring_vendors),
        payment__direction=PaymentDirection.MADE,
    ).aggregate(total=Sum("amount"))["total"]
    return (received or ZERO) - (made or ZERO)


def build_origins(org: Organization, as_of: date) -> list[BacktestOrigin]:
    earliest = (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED)
        .aggregate(d=Min("invoice_date"))["d"]
    )
    if earliest is None:
        return []
    first = earliest + timedelta(days=MIN_HISTORY_DAYS)
    last = as_of - timedelta(days=min(CHECKPOINT_DAYS))
    origins: list[BacktestOrigin] = []
    for origin_date in month_ends_between(first, last):
        vendors = recurring_vendor_keys(invoice_states(org, origin_date))
        actuals = {
            d: actual_net_flow(org, origin_date, origin_date + timedelta(days=d), vendors)
            for d in CHECKPOINT_DAYS
            if origin_date + timedelta(days=d) <= as_of
        }
        inputs = assemble_inputs(org, origin_date, for_backtest=True)
        origins.append(BacktestOrigin(inputs, actuals))
    return origins


def run_backtest(org: Organization, as_of: date, seed: int) -> BacktestResult:
    return backtest(build_origins(org, as_of), n_paths=BACKTEST_N_PATHS, seed=seed)
