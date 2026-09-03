from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import HasOrg, OrgScopedViewSet, current_org
from apps.core.throttling import ExtractionThrottle, UploadThrottle
from apps.documents import storage
from apps.documents.models import Document, DocumentStatus
from apps.documents.serializers import DocumentSerializer
from apps.documents.services import MAX_BYTES, UploadError, expand_zip, ingest_bytes


def _read(upload) -> bytes:  # type: ignore[no-untyped-def]
    if upload.size > MAX_BYTES:
        raise ValidationError("File exceeds the 25 MB limit.")
    return bytes(upload.read())


class DocumentViewSet(OrgScopedViewSet):
    queryset = Document.objects.none()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset()  # type: ignore[no-untyped-call]
        if s := self.request.query_params.get("status"):
            qs = qs.filter(status=s)
        return qs

    def _ingest(self, request: Request, name: str, data: bytes) -> dict:  # type: ignore[type-arg]
        try:
            result = ingest_bytes(
                current_org(request), data=data, filename=name, uploaded_by=request.user
            )
        except UploadError as exc:
            raise ValidationError(str(exc)) from exc
        body = dict(DocumentSerializer(result.document).data)
        body["duplicate_of"] = str(result.duplicate_of.pk) if result.duplicate_of else None
        return body

    def get_throttles(self):  # type: ignore[no-untyped-def]
        if self.action in ("create", "bulk"):
            return [UploadThrottle()]
        if self.action == "reextract":
            return [ExtractionThrottle()]
        return []

    def create(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "required"})
        body = self._ingest(request, upload.name, _read(upload))
        code = status.HTTP_200_OK if body["duplicate_of"] else status.HTTP_201_CREATED
        return Response(body, status=code)

    @action(detail=False, methods=["post"])
    def bulk(self, request: Request) -> Response:
        uploads = request.FILES.getlist("files")
        if not uploads:
            raise ValidationError({"files": "required"})
        results = []
        for upload in uploads:
            data = _read(upload)
            items = expand_zip(data) if data[:2] == b"PK" else [(upload.name, data)]
            for name, blob in items:
                try:
                    results.append(self._ingest(request, name, blob))
                except ValidationError as exc:
                    results.append({"original_filename": name, "error": str(exc.detail)})
        return Response({"results": results}, status=status.HTTP_207_MULTI_STATUS)

    @action(detail=True, methods=["post"])
    def reextract(self, request: Request, pk: str) -> Response:
        """Queue a fresh ExtractionRun; existing runs are never mutated."""
        doc = self.get_object()
        from apps.documents.tasks import extract_document

        doc.status = DocumentStatus.PENDING
        doc.error = ""
        doc.save(update_fields=["status", "error", "updated_at"])
        extract_document.delay(str(doc.pk))
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def file(self, request: Request, pk: str) -> Response:
        doc = self.get_object()
        return Response(
            {"url": storage.signed_get_url(doc.file), "expires_in": storage.SIGNED_URL_TTL_SECONDS}
        )


class DocumentsZipView(APIView):
    """GET /api/exports/documents.zip?period=YYYY-MM|fy=YYYY-YY"""

    permission_classes = [IsAuthenticated, HasOrg]

    def get(self, request: Request) -> StreamingHttpResponse:
        from apps.documents.services.organise import build_zip

        period = request.query_params.get("period") or None
        fy = request.query_params.get("fy") or None
        resp = StreamingHttpResponse(
            build_zip(current_org(request), period=period, fy=fy), content_type="application/zip"
        )
        label = period or fy or "all"
        resp["Content-Disposition"] = f'attachment; filename="documents_{label}.zip"'
        return resp
