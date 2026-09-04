"""HTTP only; thin. PROJECT_SPECS §10 Forecast."""

from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import Throttled
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.api import HasOrg, OrgScopedViewSet, current_org
from apps.forecasting.domain.engine import DEFAULT_HORIZON_DAYS
from apps.forecasting.models import (
    ExpectedInvoice,
    FixedCashflowLine,
    ForecastRun,
    RecurringExpensePattern,
    Scenario,
)
from apps.forecasting.serializers import (
    ExpectedInvoiceSerializer,
    FixedLineSerializer,
    ForecastRunListSerializer,
    ForecastRunSerializer,
    RecurringPatternSerializer,
    RunRequestSerializer,
    ScenarioSerializer,
    result_dict,
)
from apps.forecasting.services import analytics
from apps.forecasting.services.runs import RateLimitedError, latest_run, run_forecast
from apps.forecasting.services.scenarios import run_scenario


class ForecastRunViewSet(OrgScopedViewSet):
    queryset = ForecastRun.objects.none()
    serializer_class = ForecastRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):  # type: ignore[no-untyped-def]
        return ForecastRunListSerializer if self.action == "list" else ForecastRunSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return super().get_queryset().prefetch_related("points")

    def run(self, request: Request) -> Response:
        ser = RunRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            run = run_forecast(
                current_org(request),
                horizon_days=ser.validated_data["horizon_days"],
                seed=ser.validated_data.get("seed"),
            )
        except RateLimitedError as exc:
            raise Throttled(wait=exc.retry_after_seconds) from exc
        return Response(ForecastRunSerializer(run).data, status=status.HTTP_201_CREATED)

    def latest(self, request: Request) -> Response:
        run = latest_run(current_org(request))
        if run is None:
            raise Http404
        return Response(ForecastRunSerializer(run).data)

    def drivers(self, request: Request) -> Response:
        from django.utils import timezone

        from apps.forecasting.services.drivers import drivers

        return Response(drivers(current_org(request), timezone.localdate()))

    def narrative(self, request: Request, pk: str) -> Response:
        """§8.8: generate (or regenerate) the labelled summary from aggregates only."""
        from apps.forecasting.services.analytics import customer_risk
        from apps.forecasting.services.drivers import drivers
        from apps.forecasting.services.narrative import aggregates_for, generate_narrative

        run = self.get_object()
        high = [r["party_name"] for r in customer_risk(run.org, run.as_of) if r["band"] == "high"]
        agg = aggregates_for(run, drivers=drivers(run.org, run.as_of), high_risk=high)
        text = generate_narrative(run, agg)
        return Response(
            {"narrative": text, "generated": text is not None, "label": "Generated summary"}
        )

    def backtest(self, request: Request) -> Response:
        run = latest_run(current_org(request))
        if run is None:
            raise Http404
        bt = run.params.get("backtest", {})
        return Response(
            {
                "run": str(run.pk),
                "as_of": run.as_of,
                "history_days": run.history_days,
                "insufficient_history": run.insufficient_history,
                "mape": run.backtest_mape,
                "coverage": run.backtest_coverage,
                "n_origins": run.backtest_n_origins,
                "is_calibrated": bt.get("is_calibrated"),
                "checkpoints": bt.get("checkpoints", []),
            }
        )


class ScenarioViewSet(OrgScopedViewSet):
    queryset = Scenario.objects.none()
    serializer_class = ScenarioSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    @action(detail=True, methods=["post"], permission_classes=[HasOrg])
    def run(self, request: Request, pk: str) -> Response:
        """Overlay for the UI; persists nothing, so every org member may run it."""
        scenario = self.get_object()
        org = current_org(request)
        base = latest_run(org)
        result = run_scenario(
            org,
            scenario,
            horizon_days=base.horizon_days if base else DEFAULT_HORIZON_DAYS,
            seed=base.seed if base else timezone.localdate().toordinal(),
        )
        return Response(
            {
                "scenario": str(scenario.pk),
                "base_run": str(base.pk) if base else None,
                **result_dict(result),
            }
        )


class RecurringPatternViewSet(OrgScopedViewSet):
    queryset = RecurringExpensePattern.objects.none()
    serializer_class = RecurringPatternSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return super().get_queryset().select_related("party", "category")


class FixedLineViewSet(OrgScopedViewSet):
    queryset = FixedCashflowLine.objects.none()
    serializer_class = FixedLineSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]


class ExpectedInvoiceViewSet(OrgScopedViewSet):
    queryset = ExpectedInvoice.objects.none()
    serializer_class = ExpectedInvoiceSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return super().get_queryset().select_related("party")


class ForecastAnalyticsViewSet(OrgScopedViewSet):
    """Read-only computed views (§8.5); org-scoped through the services."""

    queryset = ForecastRun.objects.none()
    serializer_class = ForecastRunListSerializer
    http_method_names = ["get", "head", "options"]

    def customers(self, request: Request) -> Response:
        return Response(analytics.customer_risk(current_org(request), timezone.localdate()))

    def anomalies(self, request: Request) -> Response:
        return Response(analytics.anomalies(current_org(request), timezone.localdate()))
