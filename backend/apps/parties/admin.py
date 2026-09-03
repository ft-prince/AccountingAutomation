from django.contrib import admin

from apps.parties.models import ExpenseCategory, Party


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "org", "kind", "gstin", "state_code", "is_active", "merged_into")
    list_filter = ("kind", "is_active")
    search_fields = ("legal_name", "display_name", "gstin", "primary_email")


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "org", "itc_eligible", "section_17_5_ref", "tally_ledger_name")
    list_filter = ("itc_eligible",)
