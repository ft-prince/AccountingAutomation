from django.contrib import admin

from apps.payments.models import BankAccount, BankTransaction, Payment, PaymentAllocation


class AllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("date", "org", "party", "direction", "amount", "method", "reference")
    list_filter = ("direction", "method")
    inlines = [AllocationInline]


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "org", "bank", "masked_account", "is_active")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "bank_account", "amount", "description", "match_status")
    list_filter = ("match_status",)
    search_fields = ("description", "reference")
