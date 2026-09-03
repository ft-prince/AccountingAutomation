from decimal import Decimal

from rest_framework import serializers

from apps.invoices.models import Invoice, InvoiceLine, ValidationIssue


class LineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "line_no",
            "description",
            "hsn_sac",
            "quantity",
            "uom",
            "unit_price",
            "discount",
            "taxable_value",
            "rate",
            "cess_rate",
            "cgst",
            "sgst",
            "igst",
            "cess",
            "line_total",
            "category",
            "confidence",
        ]


class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationIssue
        fields = [
            "id",
            "code",
            "severity",
            "field",
            "message",
            "resolved_by",
            "resolved_at",
            "note",
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.legal_name", read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    issue_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "invoice_date",
            "due_date",
            "direction",
            "party",
            "party_name",
            "supply_type",
            "taxable_value",
            "cgst",
            "sgst",
            "igst",
            "cess",
            "total",
            "amount_paid",
            "outstanding",
            "payment_status",
            "status",
            "validation_status",
            "confidence",
            "fy",
            "period_month",
            "issue_count",
            "created_at",
        ]


class InvoiceDetailSerializer(InvoiceListSerializer):
    lines = LineSerializer(many=True, read_only=True)
    issues = IssueSerializer(many=True, read_only=True)
    document = serializers.UUIDField(source="document_id", read_only=True)

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + [
            "lines",
            "issues",
            "document",
            "extraction_run",
            "gstin_profile",
            "place_of_supply_state_code",
            "is_reverse_charge",
            "irn",
            "has_qr",
            "currency",
            "round_off",
            "itc_eligible",
            "itc_blocked_reason",
            "duplicate_of",
            "reviewed_by",
            "reviewed_at",
            "notes",
            "bank_details",
            "payment_terms",
            "layout_hash",
            "updated_at",
        ]


class LineWriteSerializer(serializers.Serializer):
    description = serializers.CharField(allow_blank=True, required=False, default="")
    hsn_sac = serializers.CharField(allow_blank=True, required=False, default="")
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, default=Decimal("1"))
    uom = serializers.CharField(allow_blank=True, required=False, default="")
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    cess_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))


class InvoicePatchSerializer(serializers.ModelSerializer):
    lines = LineWriteSerializer(many=True, required=False)

    class Meta:
        model = Invoice
        fields = [
            "invoice_number",
            "invoice_date",
            "due_date",
            "place_of_supply_state_code",
            "supply_type",
            "is_reverse_charge",
            "irn",
            "has_qr",
            "party",
            "itc_eligible",
            "itc_blocked_reason",
            "notes",
            "payment_terms",
            "lines",
        ]
        extra_kwargs = {f: {"required": False} for f in fields}

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        if "amount_paid" in self.initial_data or "payment_status" in self.initial_data:
            raise serializers.ValidationError(
                "amount_paid and payment_status are derived from allocations."
            )
        if attrs.get("itc_eligible") is False and not attrs.get("itc_blocked_reason"):
            raise serializers.ValidationError(
                {"itc_blocked_reason": "Required when blocking ITC (§3.7)."}
            )
        return attrs


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    force = serializers.BooleanField(required=False, default=False)


class DuplicateSerializer(serializers.Serializer):
    duplicate_of = serializers.UUIDField(required=False)


class BulkSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    force = serializers.BooleanField(required=False, default=False)
