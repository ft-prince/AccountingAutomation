from datetime import date
from decimal import Decimal

import factory

from apps.accounts.factories import OrganizationFactory
from apps.invoices.models import Invoice, InvoiceLine
from apps.parties.factories import PartyFactory


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invoice

    org = factory.SubFactory(OrganizationFactory)
    party = factory.LazyAttribute(lambda o: PartyFactory(org=o.org))
    direction = "inward"
    invoice_number = factory.Sequence(lambda n: f"INV-{n:04d}")
    invoice_date = date(2026, 7, 15)
    due_date = date(2026, 8, 14)
    supply_type = "intra"
    taxable_value = Decimal("10000.00")
    cgst = Decimal("900.00")
    sgst = Decimal("900.00")
    total = Decimal("11800.00")
    fy = "2026-27"
    period_month = "2026-07"
    status = "needs_review"
    confidence = Decimal("0.900")


class LineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvoiceLine

    invoice = factory.SubFactory(InvoiceFactory)
    line_no = 1
    description = "Widget"
    hsn_sac = "8543"
    quantity = Decimal("1")
    unit_price = Decimal("10000.00")
    taxable_value = Decimal("10000.00")
    rate = Decimal("18")
    cgst = Decimal("900.00")
    sgst = Decimal("900.00")
    line_total = Decimal("11800.00")
