from django.contrib import admin

from apps.documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "org", "mime", "status", "page_count", "created_at")
    list_filter = ("status", "mime", "source")
    search_fields = ("original_filename", "sha256")
