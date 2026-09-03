"""DRF building blocks: org-scoped viewset, role permission, RFC 7807 errors."""

from typing import Any

from django.http import Http404
from rest_framework import permissions, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.accounts.models import Organization, OrgMembership, Role
from apps.core.pagination import DefaultCursorPagination


def current_org(request: Any) -> Organization:
    org = getattr(request, "org", None)
    if org is None:
        raise Http404
    return org


def current_membership(request: Any) -> OrgMembership | None:
    return getattr(request, "membership", None)


class HasOrg(permissions.BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        return bool(request.user.is_authenticated and getattr(request, "org", None))


def require_role(*roles: str) -> type[permissions.BasePermission]:
    class RequireRole(permissions.BasePermission):
        message = f"Requires one of: {', '.join(roles)}"

        def has_permission(self, request: Request, view: Any) -> bool:
            membership = getattr(request, "membership", None)
            return bool(membership and membership.role in roles)

    return RequireRole


WRITE_ROLES = (Role.OWNER, Role.ACCOUNTANT)


class OrgScopedViewSet(viewsets.ModelViewSet):
    """Every queryset goes through TenantManager.for_org. Cross-org ids are 404, never 403."""

    permission_classes = [HasOrg]
    pagination_class = DefaultCursorPagination
    write_roles: tuple[str, ...] = WRITE_ROLES

    def get_queryset(self):  # type: ignore[no-untyped-def]
        assert self.queryset is not None
        return self.queryset.model.objects.for_org(current_org(self.request))

    def get_permissions(self):  # type: ignore[no-untyped-def]
        perms = list(super().get_permissions())
        if self.request.method not in permissions.SAFE_METHODS:
            perms.append(require_role(*self.write_roles)())
        return perms

    def perform_create(self, serializer):  # type: ignore[no-untyped-def]
        serializer.save(org=current_org(self.request))


def problem_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """RFC 7807 envelope for every DRF error."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    status = response.status_code
    title = {401: "Unauthorized", 403: "Forbidden", 404: "Not Found"}.get(status, "Request failed")
    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    if isinstance(response.data, list):
        detail = "; ".join(str(x) for x in response.data)
    body: dict[str, Any] = {"type": "about:blank", "title": title, "status": status}
    if detail is not None:
        body["detail"] = str(detail)
    if isinstance(response.data, dict) and detail is None:
        body["errors"] = response.data
    response.data = body
    response["Content-Type"] = "application/problem+json"
    return response
