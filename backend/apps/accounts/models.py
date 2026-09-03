"""Persistence only. PROJECT_SPECS §4: Organization, GSTINProfile, User, OrgMembership."""

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.core.models import BaseModel, TenantManager


class Role(models.TextChoices):
    OWNER = "owner"
    ACCOUNTANT = "accountant"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class AATOBracket(models.TextChoices):
    BELOW_5CR = "below_5cr", "Below ₹5 crore"
    FROM_5_TO_10CR = "5_to_10cr", "₹5–10 crore"
    ABOVE_10CR = "above_10cr", "Above ₹10 crore"


class Organization(BaseModel):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    aato_bracket = models.CharField(
        max_length=20, choices=AATOBracket.choices, default=AATOBracket.BELOW_5CR
    )
    brand_display_name = models.CharField(max_length=100, default="Nexren Finance")
    settings = models.JSONField(default=dict, blank=True)  # extraction toggles, auto-confirm flag

    def __str__(self) -> str:
        return self.name


class RegistrationType(models.TextChoices):
    REGULAR = "regular"
    COMPOSITION = "composition"
    CASUAL = "casual"
    SEZ = "sez"
    UNREGISTERED = "unregistered"


class GSTINProfile(BaseModel):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="gstins")
    gstin = models.CharField(max_length=15, unique=True)
    state_code = models.CharField(max_length=2)
    trade_name = models.CharField(max_length=200, blank=True)
    registration_type = models.CharField(
        max_length=20, choices=RegistrationType.choices, default=RegistrationType.REGULAR
    )
    is_default = models.BooleanField(default=False)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    objects = TenantManager()

    def __str__(self) -> str:
        return self.gstin


class UserManager(BaseUserManager["User"]):
    def create_user(self, email: str, password: str | None = None, **extra: object) -> "User":
        if not email:
            raise ValueError("email required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra: object) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []  # type: ignore[misc]
    objects = UserManager()  # type: ignore[misc]

    def __str__(self) -> str:
        return self.email


class OrgMembership(BaseModel):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    objects = TenantManager()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["org", "user"], name="uq_membership_org_user")
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.org} ({self.role})"
