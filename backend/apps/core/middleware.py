from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.accounts.models import OrgMembership


class CurrentOrgMiddleware:
    """Attach request.org and request.membership from the session's org, else the first one."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.org = None  # type: ignore[attr-defined]
        request.membership = None  # type: ignore[attr-defined]
        if request.user.is_authenticated:
            qs = OrgMembership.objects.filter(user=request.user).select_related("org")
            org_id = request.session.get("org_id")
            membership = (qs.filter(org_id=org_id).first() if org_id else None) or qs.order_by(
                "created_at"
            ).first()
            if membership:
                request.org = membership.org  # type: ignore[attr-defined]
                request.membership = membership  # type: ignore[attr-defined]
        return self.get_response(request)
