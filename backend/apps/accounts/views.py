from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import APIKey, GSTINProfile, OrgMembership, Role, User
from apps.accounts.serializers import (
    SETTINGS_KEYS,
    APIKeySerializer,
    GSTINProfileSerializer,
    LoginSerializer,
    MembershipSerializer,
    MemberWriteSerializer,
    MeSerializer,
    OkSerializer,
    OrganizationSerializer,
    SettingsSerializer,
    SwitchOrgSerializer,
)
from apps.core.api import HasOrg, OrgScopedViewSet, current_membership, current_org, require_role


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list[type] = []

    @extend_schema(request=LoginSerializer, responses={200: OkSerializer})
    def post(self, request: Request) -> Response:
        ser = LoginSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        login(request._request, ser.validated_data["user"])
        return Response({"ok": True})


class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request: Request) -> Response:
        memberships = OrgMembership.objects.filter(user=request.user).select_related("org")
        membership = current_membership(request)
        data = {
            "user": request.user,
            "org": getattr(request, "org", None),
            "role": membership.role if membership else None,
            "orgs": [
                {"id": str(m.org_id), "name": m.org.name, "role": m.role} for m in memberships
            ],
        }
        return Response(MeSerializer(data).data)

    @extend_schema(request=SwitchOrgSerializer, responses={200: OkSerializer})
    def post(self, request: Request) -> Response:
        """Switch current org: {"org_id": ...}"""
        org_id = request.data.get("org_id") if isinstance(request.data, dict) else None
        if not OrgMembership.objects.filter(user=request.user, org_id=org_id).exists():
            return Response(status=status.HTTP_404_NOT_FOUND)
        request.session["org_id"] = str(org_id)
        return Response({"ok": True})


class CurrentOrgView(APIView):
    permission_classes = [HasOrg]

    def get(self, request: Request) -> Response:
        return Response(OrganizationSerializer(current_org(request)).data)

    def patch(self, request: Request) -> Response:
        membership = current_membership(request)
        if not membership or membership.role != Role.OWNER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        ser = OrganizationSerializer(current_org(request), data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request: Request) -> Response:
        """§12: owner requests deletion; purge_deleted_orgs (Beat) removes S3 + DB after 30 days."""
        membership = current_membership(request)
        if not membership or membership.role != Role.OWNER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        from django.utils import timezone

        from apps.core.audit import record

        org = current_org(request)
        org.deletion_requested_at = timezone.now()
        org.save(update_fields=["deletion_requested_at", "updated_at"])
        record(org, actor=request.user, entity=org, action="org.deletion_requested")
        return Response(
            {"deletion_requested_at": org.deletion_requested_at, "purge_after_days": 30},
            status=status.HTTP_202_ACCEPTED,
        )


class SettingsView(APIView):
    """GET|PUT /api/settings — extraction toggles and the auto-confirm flag (§5, default OFF)."""

    permission_classes = [HasOrg]

    def get(self, request: Request) -> Response:
        org = current_org(request)
        return Response({k: org.settings.get(k, False) for k in SETTINGS_KEYS})

    def put(self, request: Request) -> Response:
        membership = current_membership(request)
        if not membership or membership.role != Role.OWNER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        ser = SettingsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = current_org(request)
        from apps.core.audit import record

        before = dict(org.settings)
        org.settings = {**org.settings, **ser.validated_data}
        org.save(update_fields=["settings", "updated_at"])
        record(
            org,
            actor=request.user,
            entity=org,
            action="org.settings",
            before=before,
            after=org.settings,
        )
        return Response({k: org.settings.get(k, False) for k in SETTINGS_KEYS})


class APIKeyViewSet(OrgScopedViewSet):
    queryset = APIKey.objects.none()
    serializer_class = APIKeySerializer
    write_roles = (Role.OWNER,)
    http_method_names = ["get", "post", "delete", "head", "options"]

    def create(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        from apps.accounts.api_keys import issue

        name = str(request.data.get("name", "")) if isinstance(request.data, dict) else ""
        if not name:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"name": "required"})
        key, raw = issue(current_org(request), name, request.user)
        return Response({**APIKeySerializer(key).data, "key": raw}, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance: APIKey) -> None:
        from django.utils import timezone

        instance.revoked_at = timezone.now()
        instance.save(update_fields=["revoked_at", "updated_at"])


class GSTINProfileViewSet(OrgScopedViewSet):
    queryset = GSTINProfile.objects.none()
    serializer_class = GSTINProfileSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]


class MemberViewSet(OrgScopedViewSet):
    queryset = OrgMembership.objects.none()
    serializer_class = MembershipSerializer
    write_roles = (Role.OWNER,)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return super().get_queryset().select_related("user")  # type: ignore[no-untyped-call]

    def create(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        ser = MemberWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user, _ = User.objects.get_or_create(email=ser.validated_data["email"])
        membership, created = OrgMembership.objects.get_or_create(
            org=current_org(request), user=user, defaults={"role": ser.validated_data["role"]}
        )
        if not created:
            return Response({"detail": "Already a member."}, status=status.HTTP_409_CONFLICT)
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance: OrgMembership) -> None:
        owners = OrgMembership.objects.for_org(instance.org).filter(role=Role.OWNER)
        if instance.role == Role.OWNER and owners.count() == 1:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Cannot remove the last owner.")
        instance.delete()


ReviewerOnlyPermission = require_role(Role.OWNER, Role.ACCOUNTANT, Role.REVIEWER)
