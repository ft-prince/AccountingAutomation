from django.contrib import admin

from apps.accounts.models import GSTINProfile, Organization, OrgMembership, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "legal_name", "pan", "aato_bracket", "created_at")
    search_fields = ("name", "legal_name", "pan")


@admin.register(GSTINProfile)
class GSTINProfileAdmin(admin.ModelAdmin):
    list_display = ("gstin", "org", "state_code", "registration_type", "is_default")
    list_filter = ("registration_type", "state_code")
    search_fields = ("gstin", "trade_name")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "is_active", "is_staff", "created_at")
    search_fields = ("email", "full_name")


@admin.register(OrgMembership)
class OrgMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "org", "role", "created_at")
    list_filter = ("role",)
