from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.api import OrgScopedViewSet, current_org
from apps.parties.models import ExpenseCategory, Party
from apps.parties.serializers import CategorySerializer, MergeSerializer, PartySerializer
from apps.parties.services import MergeError, merge_party


class PartyViewSet(OrgScopedViewSet):
    queryset = Party.objects.none()
    serializer_class = PartySerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset()  # type: ignore[no-untyped-call]
        params = self.request.query_params
        if q := params.get("q"):
            qs = qs.filter(
                Q(legal_name__icontains=q)
                | Q(display_name__icontains=q)
                | Q(gstin__icontains=q)
                | Q(primary_email__icontains=q)
            )
        if kind := params.get("kind"):
            qs = qs.filter(Q(kind=kind) | Q(kind="both"))
        if params.get("include_inactive") != "1":
            qs = qs.filter(is_active=True)
        return qs.order_by("legal_name", "-created_at")

    @action(detail=True, methods=["post"])
    def merge(self, request: Request, pk: str) -> Response:
        source = self.get_object()
        ser = MergeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        target = (
            Party.objects.for_org(current_org(request))
            .filter(pk=ser.validated_data["target"])
            .first()
        )
        if target is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            merge_party(source, target, actor=request.user)
        except MergeError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PartySerializer(target).data)


class CategoryViewSet(OrgScopedViewSet):
    queryset = ExpenseCategory.objects.none()
    serializer_class = CategorySerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        org = current_org(self.request)
        return ExpenseCategory.objects.filter(Q(org=org) | Q(org__isnull=True)).order_by("name")

    def perform_update(self, serializer):  # type: ignore[no-untyped-def]
        if serializer.instance.org_id is None:
            raise ValidationError("System categories are read-only.")
        serializer.save()

    def perform_destroy(self, instance: ExpenseCategory) -> None:
        if instance.org_id is None:
            raise ValidationError("System categories cannot be deleted.")
        instance.delete()
