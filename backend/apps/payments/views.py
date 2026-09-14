from typing import Any

from django.db.models import Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.core.api import OrgScopedViewSet, current_org, require_role
from apps.core.audit import record
from apps.invoices.models import Invoice
from apps.payments.models import (
    BankAccount,
    BankBalanceSnapshot,
    BankStatementImport,
    BankTransaction,
    MatchStatus,
    Payment,
)
from apps.payments.serializers import (
    AllocateSerializer,
    BankAccountSerializer,
    ImportSerializer,
    MatchSerializer,
    PaymentSerializer,
    SnapshotSerializer,
    TransactionSerializer,
)
from apps.payments.services import matching
from apps.payments.services.allocation import AllocationError, allocate
from apps.payments.services.statement_readers import format_for
from apps.payments.services.statements import MAPPINGS, StatementError, import_statement

WRITE = (Role.OWNER, Role.ACCOUNTANT)


class PaymentViewSet(OrgScopedViewSet):
    queryset = Payment.objects.none()
    serializer_class = PaymentSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = (
            super()
            .get_queryset()
            .select_related("party")
            .annotate(allocated=Sum("allocations__amount"))
        )  # type: ignore[no-untyped-call]
        p = self.request.query_params
        if v := p.get("direction"):
            qs = qs.filter(direction=v)
        if v := p.get("party"):
            qs = qs.filter(party_id=v)
        if p.get("unallocated") == "1":
            qs = [x for x in qs if (x.allocated or 0) < x.amount]  # small lists; fine for v1
        return qs

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        payment = serializer.save(org=current_org(self.request), created_by=self.request.user)
        record(
            payment.org,
            actor=self.request.user,
            entity=payment,
            action="payment.create",
            after={"amount": str(payment.amount)},
        )

    @action(detail=True, methods=["post"], permission_classes=[require_role(*WRITE)])
    def allocate(self, request: Request, pk: str) -> Response:
        payment = self.get_object()
        ser = AllocateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = [i["invoice"] for i in ser.validated_data["items"]]
        invoices = {
            i.pk: i for i in Invoice.objects.for_org(current_org(request)).filter(pk__in=ids)
        }
        if len(invoices) != len(set(ids)):
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            allocate(
                payment,
                [(invoices[i["invoice"]], i["amount"]) for i in ser.validated_data["items"]],
                actor=request.user,
            )
        except AllocationError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PaymentSerializer(self.get_queryset().get(pk=pk)).data)


class BankAccountViewSet(OrgScopedViewSet):
    queryset = BankAccount.objects.none()
    serializer_class = BankAccountSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]


class SnapshotViewSet(OrgScopedViewSet):
    queryset = BankBalanceSnapshot.objects.none()
    serializer_class = SnapshotSerializer
    http_method_names = ["get", "post", "head", "options"]


class ImportViewSet(OrgScopedViewSet):
    """Statement import history, newest first (org-scoped through the bank account)."""

    queryset = BankStatementImport.objects.none()
    serializer_class = ImportSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return (
            BankStatementImport.objects.filter(bank_account__org=current_org(self.request))
            .select_related("bank_account")
            .order_by("-created_at")
        )


class TransactionViewSet(OrgScopedViewSet):
    """Org-scoped through the bank account (BankTransaction has no org column)."""

    queryset = BankTransaction.objects.none()
    serializer_class = TransactionSerializer
    http_method_names = ["get", "post", "head", "options"]
    parser_classes = [JSONParser, MultiPartParser]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = BankTransaction.objects.filter(
            bank_account__org=current_org(self.request)
        ).select_related("bank_account")
        p = self.request.query_params
        if v := p.get("status"):
            qs = qs.filter(match_status=v)
        if v := p.get("account"):
            qs = qs.filter(bank_account__pk=v)
        return qs

    @action(detail=True, methods=["get"])
    def candidates(self, request: Request, pk: str) -> Response:
        txn = self.get_object()
        cands = matching.candidates_for(txn)
        return Response(
            [
                {
                    "score": str(c.score),
                    "amount": str(c.amount),
                    "reasons": c.reasons,
                    "invoices": [
                        {
                            "id": str(i.pk),
                            "invoice_number": i.invoice_number,
                            "party": i.party.legal_name,
                            "outstanding": str(i.total - i.amount_paid),
                            "due_date": i.due_date,
                        }
                        for i in c.invoices
                    ],
                }
                for c in cands
            ]
        )

    @action(detail=True, methods=["post"], permission_classes=[require_role(*WRITE)])
    def match(self, request: Request, pk: str) -> Response:
        txn = self.get_object()
        ser = MatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        invs = list(
            Invoice.objects.for_org(current_org(request))
            .filter(pk__in=ser.validated_data["invoices"])
            .select_related("party")
        )
        if len(invs) != len(ser.validated_data["invoices"]):
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            matching.apply_match(txn, invs, actor=request.user, status=MatchStatus.MANUAL)
        except (ValueError, AllocationError) as exc:
            raise ValidationError(str(exc)) from exc
        txn.refresh_from_db()
        return Response(TransactionSerializer(txn).data)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*WRITE)])
    def ignore(self, request: Request, pk: str) -> Response:
        txn = self.get_object()
        txn.match_status = MatchStatus.IGNORED
        txn.save(update_fields=["match_status", "updated_at"])
        record(current_org(request), actor=request.user, entity=txn, action="bank.ignore")
        return Response(TransactionSerializer(txn).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="auto-match",
        permission_classes=[require_role(*WRITE)],
    )
    def auto_match(self, request: Request) -> Response:
        account = (
            BankAccount.objects.for_org(current_org(request))
            .filter(pk=request.query_params.get("account"))
            .first()
        )
        if account is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(matching.auto_match(account.pk, actor=request.user))

    @action(
        detail=False, methods=["post"], url_path="import", permission_classes=[require_role(*WRITE)]
    )
    def import_statement(self, request: Request) -> Response:
        upload = request.FILES.get("file")
        form: dict[str, Any] = dict(request.data) if hasattr(request.data, "keys") else {}
        form = {k: (v[0] if isinstance(v, list) else v) for k, v in form.items()}
        account = (
            BankAccount.objects.for_org(current_org(request)).filter(pk=form.get("account")).first()
        )
        if upload is None or account is None:
            raise ValidationError({"file": "required", "account": "required"})
        data = upload.read()
        mapping_key = form.get("mapping") or None
        if mapping_key and mapping_key not in MAPPINGS:
            raise ValidationError({"mapping": f"unknown mapping {mapping_key!r}"})
        try:
            imp = import_statement(
                account,
                data=data,
                filename=upload.name,
                fmt=format_for(upload.name, data),
                actor=request.user,
                mapping_key=mapping_key,
                password=str(form.get("password") or "") or None,
            )
        except StatementError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(ImportSerializer(imp).data, status=status.HTTP_201_CREATED)
