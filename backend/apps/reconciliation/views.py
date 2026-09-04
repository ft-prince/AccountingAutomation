"""HTTP only. PROJECT_SPECS §10 Reconciliation."""

from decimal import Decimal
from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.core.api import OrgScopedViewSet, current_org, require_role
from apps.invoices.models import Invoice
from apps.reconciliation import services
from apps.reconciliation.domain.matching import MATCH_TYPES
from apps.reconciliation.models import GSTR2BBatch, GSTR2BRecord, ReconciliationMatch
from apps.reconciliation.serializers import (
    BatchSerializer,
    ImportSerializer,
    IMSSerializer,
    MatchPatchSerializer,
    MatchSerializer,
    RecordSerializer,
    RunSerializer,
)

IMPORT_ROLES = (Role.OWNER, Role.ACCOUNTANT)
UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024  # §12 file cap


def _grouped_matches(batch: GSTR2BBatch) -> tuple[dict[str, list[dict[str, Any]]], Decimal]:
    """Matches grouped by type, each row carrying its own at_risk and a running total."""
    grouped: dict[str, list[dict[str, Any]]] = {t: [] for t in MATCH_TYPES}
    running = Decimal("0")
    rows = batch.matches.select_related("record", "invoice", "invoice__party").order_by(
        "created_at"
    )
    by_type: dict[str, list[ReconciliationMatch]] = {t: [] for t in MATCH_TYPES}
    for m in rows:
        by_type.setdefault(m.match_type, []).append(m)
    for match_type in MATCH_TYPES:
        for m in by_type[match_type]:
            data = dict(MatchSerializer(m).data)
            running += services.match_at_risk(m)
            data["running_itc_at_risk"] = str(running)
            grouped[match_type].append(data)
    return grouped, running


class BatchViewSet(OrgScopedViewSet):
    queryset = GSTR2BBatch.objects.none()
    serializer_class = BatchSerializer
    http_method_names = ["get", "post", "head", "options"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset().select_related("imported_by")  # type: ignore[no-untyped-call]
        if period := self.request.query_params.get("period"):
            qs = qs.filter(period=period)
        return qs

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed("POST", detail="Use /api/reconciliation/import-2b/")

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        batch = self.get_object()
        grouped, total = _grouped_matches(batch)
        records = RecordSerializer(batch.records.all(), many=True).data
        return Response(
            {
                "batch": BatchSerializer(batch).data,
                "counts": batch.counts,
                "itc_at_risk": str(total),
                "records": records,
                "matches": grouped,
            }
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="import-2b",
        permission_classes=[require_role(*IMPORT_ROLES)],
    )
    def import_2b(self, request: Request) -> Response:
        ser = ImportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        upload = ser.validated_data["file"]
        if upload.size > UPLOAD_LIMIT_BYTES:
            raise ValidationError({"file": "file exceeds 25 MB"})
        try:
            batch = services.import_2b(
                current_org(request),
                data=upload.read(),
                filename=upload.name,
                period=ser.validated_data["period"],
                actor=request.user,
            )
        except services.ReconciliationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], permission_classes=[require_role(*IMPORT_ROLES)])
    def run(self, request: Request) -> Response:
        body = request.data if isinstance(request.data, dict) else {}
        params = {**request.query_params.dict(), **body}
        ser = RunSerializer(data=params)
        ser.is_valid(raise_exception=True)
        qs = self.get_queryset()
        if batch_id := ser.validated_data.get("batch"):
            batch = qs.filter(pk=batch_id).first()
        else:
            batch = qs.filter(period=ser.validated_data["period"]).order_by("-imported_at").first()
        if batch is None:
            raise NotFound("batch not found")
        try:
            services.run_reconciliation(batch, actor=request.user)
        except services.ReconciliationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(BatchSerializer(batch).data)


class RecordViewSet(OrgScopedViewSet):
    queryset = GSTR2BRecord.objects.none()
    serializer_class = RecordSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset()  # type: ignore[no-untyped-call]
        if batch := self.request.query_params.get("batch"):
            qs = qs.filter(batch_id=batch)
        return qs

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed("POST")

    @action(detail=True, methods=["post"], permission_classes=[require_role(*IMPORT_ROLES)])
    def ims(self, request: Request, pk: str) -> Response:
        ser = IMSSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rec = services.set_ims_action(
            self.get_object(),
            action=ser.validated_data["action"],
            note=ser.validated_data["note"],
            actor=request.user,
        )
        return Response(RecordSerializer(rec).data)


class MatchViewSet(OrgScopedViewSet):
    queryset = ReconciliationMatch.objects.none()
    serializer_class = MatchSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = (
            super()
            .get_queryset()
            .select_related(  # type: ignore[no-untyped-call]
                "record", "invoice", "invoice__party", "resolved_by"
            )
        )
        p = self.request.query_params
        if batch := p.get("batch"):
            qs = qs.filter(batch_id=batch)
        if match_type := p.get("type"):
            qs = qs.filter(match_type=match_type)
        return qs

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        match = self.get_object()
        ser = MatchPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        invoice = None
        clear_invoice = "invoice" in data and data["invoice"] is None
        if data.get("invoice"):
            invoice = (
                Invoice.objects.for_org(current_org(request)).filter(pk=data["invoice"]).first()
            )
            if invoice is None:
                raise NotFound("invoice not found")
        try:
            services.override_match(
                match,
                actor=request.user,
                match_type=data.get("match_type"),
                note=data.get("note"),
                invoice=invoice,
                clear_invoice=clear_invoice,
            )
        except services.ReconciliationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(MatchSerializer(self.get_queryset().get(pk=match.pk)).data)
