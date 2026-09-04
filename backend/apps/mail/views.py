"""HTTP only; thin. PROJECT_SPECS §10 Mail. Every viewset is org-scoped (§12)."""

from typing import Any

from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.core.api import OrgScopedViewSet, current_membership, current_org, require_role
from apps.core.audit import record
from apps.core.throttling import DraftingThrottle
from apps.mail.models import (
    DraftStatus,
    EmailDraft,
    EmailThread,
    MailboxConnection,
    Priority,
    ReplyTemplate,
    StyleGuide,
    ThreadStatus,
)
from apps.mail.serializers import (
    DraftPatchSerializer,
    DraftRequestSerializer,
    DraftSerializer,
    FlagSerializer,
    MailboxSerializer,
    ReasonSerializer,
    ReviewQueueSerializer,
    SnoozeSerializer,
    StyleGuideSerializer,
    TemplateSerializer,
    ThreadDetailSerializer,
    ThreadListSerializer,
)
from apps.mail.services import metrics, oauth, review
from apps.mail.services.drafting import DraftError, generate_draft
from apps.mail.services.llm import LLMError
from apps.mail.services.review import REVIEW_ROLES

OWNER = (Role.OWNER,)
PRIORITY_RANK = Case(
    *[
        When(thread__priority=p, then=Value(i))
        for i, p in enumerate([Priority.URGENT, Priority.HIGH, Priority.NORMAL, Priority.LOW])
    ],
    default=Value(9),
    output_field=IntegerField(),
)


class MailViewSet(OrgScopedViewSet):
    """`path(..., ViewSet.as_view({...}))` routes never receive the @action initkwargs, so a
    declared permission_classes would silently vanish there. Apply them on every route."""

    def get_permissions(self):  # type: ignore[no-untyped-def]
        perms = super().get_permissions()  # type: ignore[no-untyped-call]
        handler = getattr(self, getattr(self, "action", "") or "", None)
        declared = getattr(handler, "kwargs", {}).get("permission_classes") or []
        present = {type(p) for p in perms}
        return [*perms, *(cls() for cls in declared if cls not in present)]


class MailboxViewSet(MailViewSet):
    queryset = MailboxConnection.objects.none()
    serializer_class = MailboxSerializer
    http_method_names = ["get", "post", "head", "options"]
    write_roles = OWNER

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise ValidationError("Use POST /api/mail/connect/{provider} to add a mailbox.")

    @action(detail=False, methods=["post"], permission_classes=[require_role(*OWNER)])
    def connect(self, request: Request, provider: str) -> Response:
        try:
            url = oauth.start_connect(request.session, org=current_org(request), provider=provider)
        except oauth.OAuthError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"authorization_url": url, "provider": provider})

    @action(detail=False, methods=["get"], permission_classes=[require_role(*OWNER)])
    def connect_callback(self, request: Request, provider: str) -> Response:
        try:
            mailbox = oauth.complete_connect(
                request.session,
                org=current_org(request),
                user=request.user,
                provider=provider,
                query={k: str(v) for k, v in request.query_params.items()},
            )
        except oauth.OAuthError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(MailboxSerializer(mailbox).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*OWNER)])
    def revoke(self, request: Request, pk: str) -> Response:
        mailbox = oauth.revoke_mailbox(self.get_object(), actor=request.user)
        return Response(MailboxSerializer(mailbox).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="grant-send-scope",
        permission_classes=[require_role(*OWNER)],
    )
    def grant_send_scope(self, request: Request, pk: str) -> Response:
        mailbox = self.get_object()
        try:
            url = oauth.start_connect(
                request.session,
                org=current_org(request),
                provider=mailbox.provider,
                mailbox=mailbox,
            )
        except oauth.OAuthError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"authorization_url": url, "provider": mailbox.provider})


class ThreadViewSet(MailViewSet):
    queryset = EmailThread.objects.none()
    serializer_class = ThreadListSerializer
    http_method_names = ["get", "post", "head", "options"]
    write_roles = REVIEW_ROLES

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed("POST")  # threads come from sync, never from the API

    def get_throttles(self):  # type: ignore[no-untyped-def]
        # §12: drafting is an LLM spend amplifier; rate-limited per org.
        return [DraftingThrottle()] if self.action == "draft" else []

    def get_serializer_class(self):  # type: ignore[no-untyped-def]
        return ThreadDetailSerializer if self.action == "retrieve" else ThreadListSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset().select_related("party")  # type: ignore[no-untyped-call]
        p = self.request.query_params
        for param, field in {"status": "status", "intent": "intent", "party": "party_id"}.items():
            if v := p.get(param):
                qs = qs.filter(**{field: v})
        if self.action == "retrieve":
            qs = qs.prefetch_related("messages", "drafts")
        return qs

    def _set_status(self, request: Request, new_status: str) -> Response:
        thread = self.get_object()
        before = {"status": thread.status}
        thread.status = new_status
        thread.save(update_fields=["status", "updated_at"])
        record(
            current_org(request),
            actor=request.user,
            entity=thread,
            action=f"thread.{new_status}",
            before=before,
            after={"status": new_status},
        )
        return Response(ThreadListSerializer(thread).data)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*REVIEW_ROLES)])
    def ignore(self, request: Request, pk: str) -> Response:
        return self._set_status(request, ThreadStatus.IGNORED)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*REVIEW_ROLES)])
    def close(self, request: Request, pk: str) -> Response:
        return self._set_status(request, ThreadStatus.CLOSED)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*REVIEW_ROLES)])
    def snooze(self, request: Request, pk: str) -> Response:
        ser = SnoozeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        until = ser.validated_data["until"]
        if until <= timezone.now():
            raise ValidationError({"until": "must be in the future"})
        thread = self.get_object()
        thread.snoozed_until = until
        thread.save(update_fields=["snoozed_until", "updated_at"])
        record(
            current_org(request),
            actor=request.user,
            entity=thread,
            action="thread.snooze",
            after={"until": until.isoformat()},
        )
        return Response(ThreadListSerializer(thread).data)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*REVIEW_ROLES)])
    def draft(self, request: Request, pk: str) -> Response:
        ser = DraftRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        thread = self.get_object()
        try:
            draft = generate_draft(
                thread,
                actor=request.user,
                instruction=ser.validated_data.get("instruction") or None,
            )
        except (DraftError, LLMError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(DraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class DraftViewSet(MailViewSet):
    queryset = EmailDraft.objects.none()
    serializer_class = DraftSerializer
    http_method_names = ["get", "patch", "post", "head", "options"]
    write_roles = REVIEW_ROLES

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed("POST")  # drafts come from POST /threads/{id}/draft

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return (
            super()
            .get_queryset()  # type: ignore[no-untyped-call]
            .select_related("thread__mailbox", "thread__party")
            .prefetch_related("revisions")
        )

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        ser = DraftPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        draft = self.get_object()
        try:
            review.edit_draft(draft, editor=request.user, body_text=ser.validated_data["body_text"])
        except review.ReviewError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(DraftSerializer(draft).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="acknowledge-flag",
        permission_classes=[require_role(*REVIEW_ROLES)],
    )
    def acknowledge_flag(self, request: Request, pk: str) -> Response:
        ser = FlagSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        draft = self.get_object()
        try:
            review.acknowledge_flag(draft, reviewer=request.user, flag=ser.validated_data["flag"])
        except review.ReviewError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(DraftSerializer(draft).data)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*REVIEW_ROLES)])
    def approve(self, request: Request, pk: str) -> Response:
        draft = self.get_object()
        try:
            review.approve(draft, reviewer=request.user)
        except review.ReviewError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(DraftSerializer(draft).data)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*REVIEW_ROLES)])
    def reject(self, request: Request, pk: str) -> Response:
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        draft = self.get_object()
        try:
            review.reject(draft, reviewer=request.user, reason=ser.validated_data["reason"])
        except review.ReviewError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(DraftSerializer(draft).data)

    @action(detail=True, methods=["post"], permission_classes=[require_role(*REVIEW_ROLES)])
    def send(self, request: Request, pk: str) -> Response:
        draft = self.get_object()
        refusal = review.send_refusal(draft, current_membership(request))
        if refusal is not None:
            kind, reason = refusal
            if kind == "role":
                raise PermissionDenied(reason)
            raise ValidationError(reason)
        from apps.mail.tasks import send_draft

        send_draft.delay(str(draft.pk), str(request.user.pk))
        draft.refresh_from_db()
        return Response(DraftSerializer(draft).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["get"], url_path="review-queue")
    def review_queue(self, request: Request) -> Response:
        now = timezone.now()
        qs = (
            self.get_queryset()
            .filter(status=DraftStatus.PENDING_REVIEW)
            .exclude(thread__snoozed_until__gt=now)
            .annotate(priority_rank=PRIORITY_RANK)
            .order_by("thread__sla_due_at", "priority_rank", "created_at")
        )
        return Response(ReviewQueueSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def metrics(self, request: Request) -> Response:
        return Response(metrics.compute(current_org(request)))


class StyleGuideViewSet(MailViewSet):
    """Singleton per org: GET|PUT /api/mail/style-guide (PUT owner-only, §4/§12)."""

    queryset = StyleGuide.objects.none()
    serializer_class = StyleGuideSerializer
    http_method_names = ["get", "put", "head", "options"]
    write_roles = OWNER

    def _guide(self, request: Request) -> StyleGuide:
        guide, _ = StyleGuide.objects.get_or_create(org=current_org(request))
        return guide

    @action(detail=False, methods=["get"])
    def retrieve_guide(self, request: Request) -> Response:
        return Response(StyleGuideSerializer(self._guide(request)).data)

    @action(detail=False, methods=["put"], permission_classes=[require_role(*OWNER)])
    def update_guide(self, request: Request) -> Response:
        guide = self._guide(request)
        ser = StyleGuideSerializer(guide, data=request.data)
        ser.is_valid(raise_exception=True)
        before = StyleGuideSerializer(guide).data
        ser.save()
        record(
            current_org(request),
            actor=request.user,
            entity=guide,
            action="style_guide.update",
            before=dict(before),
            after=dict(ser.data),
        )
        return Response(ser.data)


class TemplateViewSet(MailViewSet):
    queryset = ReplyTemplate.objects.none()
    serializer_class = TemplateSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = super().get_queryset()  # type: ignore[no-untyped-call]
        if v := self.request.query_params.get("intent"):
            qs = qs.filter(intent=v)
        return qs.order_by("intent", "name")
