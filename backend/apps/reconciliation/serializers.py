from typing import Any

from rest_framework import serializers

from apps.invoices.models import Invoice
from apps.reconciliation import services
from apps.reconciliation.models import (
    GSTR2BBatch,
    GSTR2BRecord,
    IMSAction,
    MatchType,
    ReconciliationMatch,
)


class BatchSerializer(serializers.ModelSerializer):
    imported_by: serializers.SlugRelatedField[Any] = serializers.SlugRelatedField(
        slug_field="email", read_only=True
    )

    class Meta:
        model = GSTR2BBatch
        fields = [
            "id",
            "period",
            "source",
            "filename",
            "imported_by",
            "imported_at",
            "counts",
            "created_at",
        ]
        read_only_fields = fields


class RecordSerializer(serializers.ModelSerializer):
    tax = serializers.SerializerMethodField()

    class Meta:
        model = GSTR2BRecord
        fields = [
            "id",
            "batch",
            "supplier_gstin",
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "invoice_value",
            "place_of_supply",
            "reverse_charge",
            "taxable_value",
            "igst",
            "cgst",
            "sgst",
            "cess",
            "tax",
            "itc_available",
            "ims_action",
            "ims_note",
        ]
        read_only_fields = fields

    def get_tax(self, obj: GSTR2BRecord) -> str:
        return str(services.record_tax(obj))


class InvoiceBriefSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.legal_name", read_only=True)
    party_gstin = serializers.CharField(source="party.gstin", read_only=True)
    tax = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "invoice_date",
            "party_name",
            "party_gstin",
            "taxable_value",
            "total",
            "tax",
            "itc_eligible",
            "status",
        ]
        read_only_fields = fields

    def get_tax(self, obj: Invoice) -> str:
        return str(services.invoice_tax(obj))


class MatchSerializer(serializers.ModelSerializer):
    record = RecordSerializer(read_only=True)
    invoice = InvoiceBriefSerializer(read_only=True)
    resolved_by: serializers.SlugRelatedField[Any] = serializers.SlugRelatedField(
        slug_field="email", read_only=True
    )
    at_risk = serializers.SerializerMethodField()

    class Meta:
        model = ReconciliationMatch
        fields = [
            "id",
            "batch",
            "record",
            "invoice",
            "match_type",
            "delta_value",
            "delta_tax",
            "at_risk",
            "note",
            "resolved_by",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_at_risk(self, obj: ReconciliationMatch) -> str:
        return str(services.match_at_risk(obj))


class MatchPatchSerializer(serializers.Serializer):
    match_type = serializers.ChoiceField(choices=MatchType.choices, required=False)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    invoice = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("nothing to update")
        return attrs


class ImportSerializer(serializers.Serializer):
    file = serializers.FileField()
    period = serializers.RegexField(services.PERIOD_PATTERN.pattern)


class RunSerializer(serializers.Serializer):
    batch = serializers.UUIDField(required=False)
    period = serializers.RegexField(services.PERIOD_PATTERN.pattern, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("batch") and not attrs.get("period"):
            raise serializers.ValidationError("pass batch=<id> or period=MMYYYY")
        return attrs


class IMSSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=IMSAction.choices)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
