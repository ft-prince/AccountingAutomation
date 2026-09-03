"""Persistence only. PROJECT_SPECS §4: Party, ExpenseCategory."""

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.accounts.models import AATOBracket
from apps.core.models import BaseModel, TenantManager, TenantModel


class PartyKind(models.TextChoices):
    VENDOR = "vendor"
    CUSTOMER = "customer"
    BOTH = "both"


class ExpenseCategory(BaseModel):
    org = models.ForeignKey(
        "accounts.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )  # null = system seed
    name = models.CharField(max_length=100)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    itc_eligible = models.BooleanField(default=True)
    section_17_5_ref = models.CharField(max_length=20, blank=True)
    tally_ledger_name = models.CharField(max_length=100, blank=True)
    is_recurring_hint = models.BooleanField(default=False)

    objects = TenantManager()

    class Meta(BaseModel.Meta):
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "name"], name="uq_category_org_name", nulls_distinct=False
            )
        ]

    def __str__(self) -> str:
        return self.name


class Party(TenantModel):
    kind = models.CharField(max_length=10, choices=PartyKind.choices, default=PartyKind.VENDOR)
    legal_name = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200, blank=True)
    gstin = models.CharField(max_length=15, null=True, blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    primary_email = models.EmailField(blank=True)
    email_domains = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    is_composition = models.BooleanField(default=False)
    aato_bracket = models.CharField(
        max_length=20, choices=AATOBracket.choices, default=AATOBracket.BELOW_5CR
    )
    default_category = models.ForeignKey(
        ExpenseCategory, null=True, blank=True, on_delete=models.SET_NULL
    )
    payment_terms_days = models.PositiveSmallIntegerField(default=30)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    merged_into = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_from"
    )
    is_active = models.BooleanField(default=True)

    class Meta(TenantModel.Meta):
        ordering = ["legal_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["org", "gstin"],
                condition=models.Q(gstin__isnull=False),
                name="uq_party_gstin",
            )
        ]

    def __str__(self) -> str:
        return self.display_name or self.legal_name
