from django.contrib import admin

from apps.invoices.models import Invoice, InvoiceLine, ValidationIssue


class LineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "org",
        "party",
        "direction",
        "invoice_date",
        "total",
        "status",
        "payment_status",
    )
    list_filter = ("status", "direction", "payment_status", "fy")
    search_fields = ("invoice_number", "party__legal_name")
    inlines = [LineInline]


@admin.register(ValidationIssue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("invoice", "code", "severity", "field", "resolved_at")
    list_filter = ("code", "severity")
