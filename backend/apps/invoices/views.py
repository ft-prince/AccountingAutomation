from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.core.api import OrgScopedViewSet, current_membership, current_org, require_role
from apps.invoices import services
from apps.invoices.models import Invoice, InvoiceStatus
from apps.invoices.serializers import (
    BulkSerializer,
    DuplicateSerializer,
    InvoiceCreateSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    InvoicePatchSerializer,
    IssueSerializer,
    ReasonSerializer,
)

CONFIRM_ROLES = (Role.OWNER, Role.ACCOUNTANT)


class InvoiceViewSet(OrgScopedViewSet):
    queryset = Invoice.objects.none()
    serializer_class = InvoiceListSerializer
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_serializer_class(self):  # type: ignore[no-untyped-def]
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        if self.action == "partial_update":
            return InvoicePatchSerializer
        return InvoiceListSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = (
            super()
            .get_queryset()  # type: ignore[no-untyped-call]
            .select_related("party", "extraction_run")
            .annotate(
                outstanding=F("total") - F("amount_paid"),
                issue_count=Count("issues", distinct=True),
            )
        )
        p = self.request.query_params
        simple = {
            "status": "status",
            "direction": "direction",
            "party": "party_id",
            "fy": "fy",
            "period": "period_month",
            "payment_status": "payment_status",
            "category": "lines__category_id",
            "supply_type": "supply_type",
        }
        for param, field in simple.items():
            if v := p.get(param):
                qs = qs.filter(**{field: v})
        if v := p.get("from"):
            qs = qs.filter(invoice_date__gte=v)
        if v := p.get("to"):
            qs = qs.filter(invoice_date__lte=v)
        if v := p.get("min"):
            qs = qs.filter(total__gte=v)
        if v := p.get("max"):
            qs = qs.filter(total__lte=v)
        if q := p.get("q"):
            qs = qs.filter(
                Q(invoice_number__icontains=q)
                | Q(party__legal_name__icontains=q)
                | Q(party__gstin__icontains=q)
                | Q(notes__icontains=q)
            )
        ordering = p.get("ordering", "-invoice_date")
        allowed = {
            "invoice_date",
            "total",
            "due_date",
            "confidence",
            "created_at",
            "party__legal_name",
        }
        if ordering.lstrip("-") in allowed:
            qs = qs.order_by(ordering, "-created_at")
        return qs.distinct()

    def partial_update(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        invoice = self.get_object()
        membership = current_membership(request)
        if invoice.status == InvoiceStatus.CONFIRMED and (
            membership is None or membership.role not in CONFIRM_ROLES
        ):
            raise ValidationError(
                "Confirmed invoices can only be edited by an owner or accountant."
            )
        ser = InvoicePatchSerializer(invoice, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        lines = data.pop("lines", None)
        services.apply_edit(invoice, data, lines, actor=request.user)
        return Response(InvoiceDetailSerializer(self.get_queryset().get(pk=invoice.pk)).data)

    def _confirm(self, invoice: Invoice, request: Request, force: bool) -> None:
        errors = services.unresolved_errors(invoice)
        if errors and not force:
            raise ValidationError(
                {
                    "detail": "Unresolved validation errors; pass force=true to override.",
                    "issues": IssueSerializer(errors, many=True).data,
                }
            )
        if invoice.status == InvoiceStatus.DUPLICATE:
            raise ValidationError(
                "Duplicates cannot be confirmed; reject or re-point duplicate_of."
            )
        services.set_status(
            invoice, InvoiceStatus.CONFIRMED, actor=request.user, reason="forced" if errors else ""
        )

    @action(detail=True, methods=["post"], permission_classes=[require_role(*CONFIRM_ROLES)])
    def confirm(self, request: Request, pk: str) -> Response:
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        invoice = self.get_object()
        self._confirm(invoice, request, ser.validated_data["force"])
        return Response(InvoiceDetailSerializer(self.get_queryset().get(pk=pk)).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[require_role(Role.OWNER, Role.ACCOUNTANT, Role.REVIEWER)],
    )
    def reject(self, request: Request, pk: str) -> Response:
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data["reason"]:
            raise ValidationError({"reason": "A reason is required to reject."})
        services.set_status(
            self.get_object(),
            InvoiceStatus.REJECTED,
            actor=request.user,
            reason=ser.validated_data["reason"],
        )
        return Response(InvoiceDetailSerializer(self.get_queryset().get(pk=pk)).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="mark-duplicate",
        permission_classes=[require_role(Role.OWNER, Role.ACCOUNTANT, Role.REVIEWER)],
    )
    def mark_duplicate(self, request: Request, pk: str) -> Response:
        ser = DuplicateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        invoice = self.get_object()
        target = None
        if dup_id := ser.validated_data.get("duplicate_of"):
            target = self.get_queryset().filter(pk=dup_id).first()
            if target is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
        services.set_status(
            invoice, InvoiceStatus.DUPLICATE, actor=request.user, duplicate_of=target
        )
        return Response(InvoiceDetailSerializer(self.get_queryset().get(pk=pk)).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-confirm",
        permission_classes=[require_role(*CONFIRM_ROLES)],
    )
    def bulk_confirm(self, request: Request) -> Response:
        ser = BulkSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        results = {}
        for inv in self.get_queryset().filter(
            pk__in=ser.validated_data["ids"], status=InvoiceStatus.NEEDS_REVIEW
        ):
            try:
                self._confirm(inv, request, ser.validated_data["force"])
                results[str(inv.pk)] = "confirmed"
            except ValidationError as exc:
                results[str(inv.pk)] = str(
                    exc.detail.get("detail", exc.detail)
                    if isinstance(exc.detail, dict)
                    else exc.detail
                )
        return Response({"results": results})

    def create(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        """Manual entry. Held to the same GST rules and recompute as an extracted invoice."""
        from apps.invoices.manual import ManualInvoiceError, create_manual_invoice

        ser = InvoiceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = dict(ser.validated_data)
        lines = [dict(line) for line in payload.pop("lines")]
        try:
            invoice = create_manual_invoice(
                current_org(request), payload, lines, actor=request.user
            )
        except ManualInvoiceError as exc:
            raise ValidationError(str(exc)) from exc
        detail = self.get_queryset().get(pk=invoice.pk)
        return Response(InvoiceDetailSerializer(detail).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="import", parser_classes=[MultiPartParser])
    def import_csv(self, request: Request) -> Response:
        """One row per invoice line; rows sharing an invoice_number become one invoice."""
        from apps.invoices.manual import ManualInvoiceError, import_csv

        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "required"})
        try:
            result = import_csv(current_org(request), upload.read(), actor=request.user)
        except ManualInvoiceError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result, status=status.HTTP_207_MULTI_STATUS)

    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request: Request) -> HttpResponse:
        from apps.invoices.manual import csv_template

        response = HttpResponse(csv_template(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="invoice-import-template.csv"'
        return response

    @action(detail=False, methods=["get"], url_path="review-queue")
    def review_queue(self, request: Request) -> Response:
        qs = (
            self.get_queryset()
            .filter(status=InvoiceStatus.NEEDS_REVIEW)
            .order_by("confidence", "created_at")
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(InvoiceListSerializer(page, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"issues/(?P<issue_id>[^/.]+)/resolve",
        permission_classes=[require_role(Role.OWNER, Role.ACCOUNTANT, Role.REVIEWER)],
    )
    def resolve_issue(self, request: Request, pk: str, issue_id: str) -> Response:
        invoice = self.get_object()
        issue = invoice.issues.filter(pk=issue_id).first()
        if issue is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        issue.resolved_by = request.user
        issue.resolved_at = timezone.now()
        issue.note = str(request.data.get("note", "") if isinstance(request.data, dict) else "")[
            :500
        ]
        issue.save(update_fields=["resolved_by", "resolved_at", "note", "updated_at"])
        from apps.core.audit import record

        record(
            current_org(request),
            actor=request.user,
            entity=invoice,
            action="invoice.issue_resolved",
            after={"issue": issue.code, "note": issue.note},
        )
        return Response(IssueSerializer(issue).data)
