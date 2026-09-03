from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import (
    BankAccount,
    BankBalanceSnapshot,
    BankStatementImport,
    BankTransaction,
    Payment,
    PaymentAllocation,
)


class AllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "invoice", "invoice_number", "amount"]


class PaymentSerializer(serializers.ModelSerializer):
    allocations = AllocationSerializer(many=True, read_only=True)
    allocated = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    party_name = serializers.CharField(source="party.legal_name", read_only=True, default="")

    class Meta:
        model = Payment
        fields = [
            "id",
            "party",
            "party_name",
            "direction",
            "amount",
            "date",
            "method",
            "reference",
            "notes",
            "allocations",
            "allocated",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]


class AllocateItemSerializer(serializers.Serializer):
    invoice = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class AllocateSerializer(serializers.Serializer):
    items = AllocateItemSerializer(many=True, allow_empty=False)


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "id",
            "name",
            "bank",
            "masked_account",
            "opening_balance",
            "opening_balance_date",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankStatementImport
        fields = [
            "id",
            "bank_account",
            "filename",
            "format",
            "mapping",
            "rows_total",
            "rows_imported",
            "rows_duplicate",
            "created_at",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "bank_account",
            "date",
            "amount",
            "description",
            "reference",
            "balance_after",
            "match_status",
            "matched_payment",
            "created_at",
        ]


class SnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankBalanceSnapshot
        fields = ["id", "bank_account", "date", "balance", "source", "created_at"]
        read_only_fields = ["id", "source", "created_at"]


class MatchSerializer(serializers.Serializer):
    invoices = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
