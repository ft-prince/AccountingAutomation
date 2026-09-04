"""Headline confidence now ignores soft fields (payment terms, notes, addresses).
Recompute the stored score for every extracted invoice so the review queue and the
detail screen agree with the new rule. Manual invoices (no run) are untouched."""

from decimal import Decimal

from django.db import migrations


def recompute(apps, schema_editor):
    from apps.invoices.services import core_confidence

    Invoice = apps.get_model("invoices", "Invoice")
    qs = Invoice.objects.filter(extraction_run__isnull=False).select_related("extraction_run")
    for inv in qs.iterator():
        fc = inv.extraction_run.field_confidence or {}
        if not fc:
            continue
        value, _ = core_confidence(fc)
        if inv.confidence != value:
            Invoice.objects.filter(pk=inv.pk).update(confidence=value)


class Migration(migrations.Migration):
    dependencies = [("invoices", "0001_initial"), ("documents", "0004_alter_document_status")]
    operations = [migrations.RunPython(recompute, migrations.RunPython.noop)]
