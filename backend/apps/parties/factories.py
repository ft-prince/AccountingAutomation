import factory

from apps.accounts.factories import OrganizationFactory
from apps.parties.models import ExpenseCategory, Party


class PartyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Party

    org = factory.SubFactory(OrganizationFactory)
    legal_name = factory.Sequence(lambda n: f"Party {n} Pvt Ltd")
    kind = "both"
    state_code = "27"


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ExpenseCategory

    org = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
