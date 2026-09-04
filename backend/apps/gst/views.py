"""HTTP only. PROJECT_SPECS §10 Exports: GET /api/exports/{gstr1|gstr3b|csv}.
Any org member (viewer included) may export; every export is confirmed-only and states
the needs_review count in X-Pending-Count (§7.1)."""

from django.http import HttpResponse
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.api import HasOrg, current_org
from apps.gst.exports.common import ExportError, dumps, pending_count, period_month
from apps.gst.exports.csv import build_csv
from apps.gst.exports.gstr1 import build_gstr1
from apps.gst.exports.gstr3b import build_gstr3b
from apps.invoices.models import Direction

JSON_CONTENT_TYPE = "application/json"
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"


def _attachment(body: str, content_type: str, filename: str, pending: int) -> HttpResponse:
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Pending-Count"] = str(pending)
    return response


class ExportView(APIView):
    permission_classes = [IsAuthenticated, HasOrg]

    def get(self, request: Request, kind: str) -> HttpResponse:
        org = current_org(request)
        params = {k: str(v) for k, v in request.query_params.items()}
        try:
            if kind == "gstr1":
                period = params.get("period", "")
                payload = build_gstr1(org, period)
                pending = pending_count(org, period_month(period), Direction.OUTWARD)
                name = f"GSTR1_{payload['gstin']}_{period}.json"
                return _attachment(dumps(payload), JSON_CONTENT_TYPE, name, pending)
            if kind == "gstr3b":
                period = params.get("period", "")
                payload = build_gstr3b(org, period)
                pending = pending_count(org, period_month(period))
                name = f"GSTR3B_{payload['gstin']}_{period}.json"
                return _attachment(dumps(payload), JSON_CONTENT_TYPE, name, pending)
            if kind == "csv":
                export = build_csv(org, params.get("type", ""), params)
                return _attachment(
                    export.content, CSV_CONTENT_TYPE, export.filename, export.pending
                )
        except ExportError as exc:
            raise ValidationError(str(exc)) from exc
        raise NotFound(f"Unknown export {kind!r}")
