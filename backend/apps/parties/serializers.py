from rest_framework import serializers

from apps.parties.models import ExpenseCategory, Party


class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = [
            "id",
            "kind",
            "legal_name",
            "display_name",
            "gstin",
            "state_code",
            "pan",
            "primary_email",
            "email_domains",
            "is_composition",
            "aato_bracket",
            "default_category",
            "payment_terms_days",
            "credit_limit",
            "merged_into",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "merged_into", "created_at", "updated_at"]

    def validate_gstin(self, value: str | None) -> str | None:
        if not value:
            return None
        from apps.gst.domain.gstin import validate

        result = validate(value)
        if not result.is_valid:
            raise serializers.ValidationError(result.errors)
        return value

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        gstin = attrs.get("gstin")
        if gstin:
            attrs.setdefault("state_code", gstin[:2])
            attrs.setdefault("pan", gstin[2:12])
        return attrs


class CategorySerializer(serializers.ModelSerializer):
    is_system = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseCategory
        fields = [
            "id",
            "name",
            "parent",
            "itc_eligible",
            "section_17_5_ref",
            "tally_ledger_name",
            "is_recurring_hint",
            "is_system",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_is_system(self, obj: ExpenseCategory) -> bool:
        return obj.org_id is None


class MergeSerializer(serializers.Serializer):
    target = serializers.UUIDField()
