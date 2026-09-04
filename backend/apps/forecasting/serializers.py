from datetime import date
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.core.api import current_org
from apps.forecasting.domain.engine import (
    DEFAULT_HORIZON_DAYS,
    DayPoint,
    ForecastInputs,
    ForecastResult,
    OpeningCash,
)
from apps.forecasting.domain.scenarios import ScenarioError, apply_overrides
from apps.forecasting.models import (
    ExpectedInvoice,
    FixedCashflowLine,
    ForecastPoint,
    ForecastRun,
    RecurringExpensePattern,
    Scenario,
)

MIN_HORIZON_DAYS = 7
MAX_HORIZON_DAYS = 365


def _own_org(serializer: serializers.Serializer, obj: Any, label: str) -> Any:
    org = current_org(serializer.context["request"])
    if obj is not None and obj.org_id is not None and obj.org_id != org.pk:
        raise serializers.ValidationError(f"Unknown {label}.")
    return obj


class ForecastPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastPoint
        fields = ["date", "p10", "p50", "p90", "deterministic"]


class ForecastRunListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastRun
        fields = [
            "id",
            "as_of",
            "horizon_days",
            "seed",
            "params",
            "inputs_hash",
            "history_days",
            "insufficient_history",
            "opening_cash",
            "backtest_mape",
            "backtest_coverage",
            "backtest_n_origins",
            "runway_date",
            "narrative",
            "status",
            "error",
            "created_at",
        ]
        read_only_fields = fields


class ForecastRunSerializer(ForecastRunListSerializer):
    points = ForecastPointSerializer(many=True, read_only=True)

    class Meta(ForecastRunListSerializer.Meta):
        fields = [*ForecastRunListSerializer.Meta.fields, "points"]
        read_only_fields = fields


class RunRequestSerializer(serializers.Serializer):
    horizon_days = serializers.IntegerField(
        min_value=MIN_HORIZON_DAYS, max_value=MAX_HORIZON_DAYS, default=DEFAULT_HORIZON_DAYS
    )
    seed = serializers.IntegerField(required=False, min_value=0)


class ScenarioSerializer(serializers.ModelSerializer):
    overrides = serializers.JSONField()

    class Meta:
        model = Scenario
        fields = ["id", "name", "overrides", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_overrides(self, value: Any) -> list[Any]:
        if not isinstance(value, list):
            raise serializers.ValidationError("overrides must be a list of objects.")
        try:
            apply_overrides(ForecastInputs(OpeningCash(Decimal("0"), date.today())), value)
        except ScenarioError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


def point_dict(p: DayPoint) -> dict[str, Any]:
    return {
        "date": p.date.isoformat(),
        "p10": str(p.p10) if p.p10 is not None else None,
        "p50": str(p.p50) if p.p50 is not None else None,
        "p90": str(p.p90) if p.p90 is not None else None,
        "deterministic": str(p.deterministic),
    }


def result_dict(result: ForecastResult) -> dict[str, Any]:
    return {
        "as_of": result.as_of.isoformat(),
        "horizon_days": result.horizon_days,
        "n_paths": result.n_paths,
        "seed": result.seed,
        "runway_date": result.runway_date.isoformat() if result.runway_date else None,
        "points": [point_dict(p) for p in result.points],
    }


class RecurringPatternSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.legal_name", read_only=True, default="")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")

    class Meta:
        model = RecurringExpensePattern
        fields = [
            "id",
            "party",
            "party_name",
            "category",
            "category_name",
            "amount_p50",
            "period_days",
            "next_expected",
            "confidence",
            "occurrences",
            "user_confirmed",
            "last_detected_at",
            "created_at",
        ]
        read_only_fields = ["id", "confidence", "occurrences", "last_detected_at", "created_at"]

    def validate_party(self, value: Any) -> Any:
        return _own_org(self, value, "party")

    def validate_category(self, value: Any) -> Any:
        return _own_org(self, value, "category")


class FixedLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = FixedCashflowLine
        fields = [
            "id",
            "name",
            "amount",
            "cadence",
            "next_date",
            "direction",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ExpectedInvoiceSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.legal_name", read_only=True)
    probability = serializers.DecimalField(
        max_digits=3, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("1")
    )

    class Meta:
        model = ExpectedInvoice
        fields = [
            "id",
            "party",
            "party_name",
            "amount",
            "expected_date",
            "probability",
            "note",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_party(self, value: Any) -> Any:
        return _own_org(self, value, "party")
