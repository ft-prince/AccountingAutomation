from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import HasOrg, current_org
from apps.reporting.services import REPORTS, period_from_params


class ReportView(APIView):
    """GET /api/reports/{name}?fy=&from=&to=&basis=accrual|cash"""

    permission_classes = [IsAuthenticated, HasOrg]

    def get(self, request: Request, name: str) -> Response:
        fn = REPORTS.get(name)
        if fn is None:
            raise NotFound(f"Unknown report {name!r}")
        try:
            period = period_from_params({k: str(v) for k, v in request.query_params.items()})
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(fn(current_org(request), period))
