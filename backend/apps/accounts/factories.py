import factory

from apps.accounts.models import GSTINProfile, Organization, OrgMembership, Role, User


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.django.Password("pw")


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrgMembership

    org = factory.SubFactory(OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    role = Role.OWNER


class GSTINProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GSTINProfile

    org = factory.SubFactory(OrganizationFactory)
    gstin = "27AAPFU0939F1ZV"
    state_code = "27"
