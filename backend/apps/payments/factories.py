from datetime import date
from decimal import Decimal

import factory

from apps.accounts.factories import OrganizationFactory
from apps.payments.models import BankAccount, BankTransaction, Payment


class BankAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BankAccount

    org = factory.SubFactory(OrganizationFactory)
    name = "Current A/c"
    bank = "HDFC"
    masked_account = "XXXX1234"


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    org = factory.SubFactory(OrganizationFactory)
    direction = "received"
    amount = Decimal("11800.00")
    date = date(2026, 8, 1)


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BankTransaction

    bank_account = factory.SubFactory(BankAccountFactory)
    date = date(2026, 8, 1)
    amount = Decimal("11800.00")
    description = "NEFT CR"
    sha256 = factory.Sequence(lambda n: f"{n:064d}")
