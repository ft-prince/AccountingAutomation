"""Shared plumbing for the GSTN and CSV exporters: period parsing, the org's GSTIN,
the confirmed-only queryset, and the single sanctioned Decimal→JSON-number boundary."""

import json
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Q, QuerySet

from apps.accounts.models import GSTINProfile
from apps.invoices.models import Invoice, InvoiceStatus

PERIOD_PATTERN = re.compile(r"^(0[1-9]|1[0-2])(\d{4})$")
TWO_DP = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")
GSTN_DATE_FORMAT = "%d-%m-%Y"  # GSTN schemas carry dates as DD-MM-YYYY strings


class ExportError(ValueError):
    """User-facing export failure (bad period, no GSTIN on the org)."""


def period_month(period: str) -> str:
    """ "MMYYYY" (GSTN return period) → "YYYY-MM" (Invoice.period_month)."""
    match = PERIOD_PATTERN.match(period or "")
    if match is None:
        raise ExportError(f"period must be MMYYYY, got {period!r}")
    return f"{match.group(2)}-{match.group(1)}"


def period_start(period: str) -> date:
    month_label = period_month(period)
    return date(int(month_label[:4]), int(month_label[5:]), 1)


def money(value: Decimal | int | None) -> Decimal:
    return (Decimal(value) if value is not None else ZERO).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def gstn_date(d: date) -> str:
    return d.strftime(GSTN_DATE_FORMAT)


def rate_number(rate: Decimal) -> int | Decimal:
    """GSTN wants whole rates as integers (18, not 18.0) and fractional ones as numbers."""
    quantized = rate.quantize(TWO_DP, rounding=ROUND_HALF_UP)
    return int(quantized) if quantized == quantized.to_integral_value() else quantized


def default_profile(org: Any) -> GSTINProfile:
    profile = GSTINProfile.objects.for_org(org).order_by("-is_default", "created_at").first()
    if profile is None:
        raise ExportError("the organisation has no GSTIN profile; add one under Settings")
    return profile


def confirmed_invoices(org: Any, profile: GSTINProfile, month_label: str) -> QuerySet[Invoice]:
    """Confirmed invoices of one period that belong to this GSTIN. A return is per GSTIN:
    invoices tagged to another profile are excluded; untagged ones fall to the default."""
    return (
        Invoice.objects.for_org(org)
        .filter(status=InvoiceStatus.CONFIRMED, period_month=month_label)
        .filter(Q(gstin_profile=profile) | Q(gstin_profile__isnull=True))
        .select_related("party")
        .prefetch_related("lines")
        .order_by("invoice_date", "invoice_number")
    )


def pending_count(org: Any, month_label: str, direction: str | None = None) -> int:
    qs = Invoice.objects.for_org(org).filter(
        status=InvoiceStatus.NEEDS_REVIEW, period_month=month_label
    )
    if direction:
        qs = qs.filter(direction=direction)
    return qs.count()


def to_json(value: Any) -> Any:
    """Recursively convert an export payload into plain JSON types.

    THE ONE SANCTIONED Decimal→float CONVERSION. The GSTN schemas require JSON numbers,
    not strings, for every amount, so Decimals are quantized to 2 dp HALF_UP and only
    then rendered as a float at this final serialisation boundary. Nothing upstream of
    this function may hold a float."""
    if isinstance(value, Decimal):
        return float(value.quantize(TWO_DP, rounding=ROUND_HALF_UP))
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    if isinstance(value, date):
        return gstn_date(value)
    return value


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(to_json(payload), ensure_ascii=False, separators=(",", ":"))
