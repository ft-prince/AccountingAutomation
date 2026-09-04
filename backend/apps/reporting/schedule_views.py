from rest_framework import serializers

from apps.accounts.models import Role
from apps.core.api import OrgScopedViewSet, current_org
from apps.reporting.models import ReportSchedule
from apps.reporting.schedules import request_send_scope
from apps.reporting.services import REPORTS


class ReportScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportSchedule
        fields = [
            "id",
            "report",
            "params",
            "cadence",
            "recipients",
            "format",
            "is_active",
            "last_sent_at",
            "last_error",
            "created_at",
        ]
        read_only_fields = ["id", "last_sent_at", "last_error", "created_at"]

    def validate_report(self, v: str) -> str:
        if v not in REPORTS:
            raise serializers.ValidationError(f"unknown report; one of {sorted(REPORTS)}")
        return v

    def validate_recipients(self, v: list[str]) -> list[str]:
        if not v:
            raise serializers.ValidationError("at least one recipient")
        return v


class ReportScheduleViewSet(OrgScopedViewSet):
    queryset = ReportSchedule.objects.none()
    serializer_class = ReportScheduleSerializer
    write_roles = (Role.OWNER, Role.ACCOUNTANT)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        org = current_org(self.request)
        serializer.save(org=org, created_by=self.request.user)
        request_send_scope(org)
