from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import GSTINProfile, OrgMembership, Role, User
from apps.accounts.serializers import (
    GSTINProfileSerializer,
    LoginSerializer,
    MembershipSerializer,
    MemberWriteSerializer,
    MeSerializer,
    OrganizationSerializer,
)
from apps.core.api import HasOrg, OrgScopedViewSet, current_membership, current_org, require_role


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list[type] = []

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
