from rest_framework import serializers

from apps.mail.domain.guardrails import ALL_FLAGS
from apps.mail.models import (
    DraftRevision,
    EmailDraft,
    EmailMessage,
    EmailThread,
    MailboxConnection,
    ReplyTemplate,
    StyleGuide,
)

MAX_FEW_SHOT_EXAMPLES = 20


class MailboxSerializer(serializers.ModelSerializer):
    has_send_scope = serializers.BooleanField(read_only=True)

    class Meta:
        model = MailboxConnection
        fields = [
            "id",
            "provider",
            "email_address",
            "scopes",
            "status",
            "has_send_scope",
            "needs_send_scope",
            "last_sync_at",
            "last_error",
            "connected_by",
            "created_at",
        ]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        fields = [
            "id",
            "direction",
            "from_address",
            "to_addresses",
            "cc_addresses",
            "date",
            "subject",
            "body_text",
            "body_html",
            "attachments",
            "is_read",
            "injection_flag",
            "injection_note",
        ]


class ThreadListSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.legal_name", read_only=True, default="")

    class Meta:
        model = EmailThread
        fields = [
            "id",
            "mailbox",
            "subject",
            "party",
            "party_name",
            "party_resolution",
            "linked_invoices",
            "intent",
            "priority",
            "sentiment",
            "requires_finance_data",
            "status",
            "last_inbound_at",
            "sla_due_at",
            "snoozed_until",
            "created_at",
        ]


class RevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DraftRevision
        fields = ["id", "editor", "before", "after", "created_at"]


class DraftSerializer(serializers.ModelSerializer):
    revisions = RevisionSerializer(many=True, read_only=True)

    class Meta:
        model = EmailDraft
        fields = [
            "id",
            "thread",
            "in_reply_to",
            "version",
            "prompt_version",
            "model_name",
            "context_snapshot",
            "body_text",
            "body_html",
            "proposed_attachments",
            "tone",
            "confidence",
            "guardrail_flags",
            "acknowledged_flags",
            "status",
            "instruction",
            "created_by",
            "reviewed_by",
            "reviewed_at",
            "reject_reason",
            "sent_message",
            "sent_at",
            "edit_distance",
            "revisions",
            "created_at",
        ]
        read_only_fields = fields


class DraftSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailDraft
        fields = [
            "id",
            "version",
            "status",
            "tone",
            "confidence",
            "guardrail_flags",
            "acknowledged_flags",
            "reviewed_by",
            "sent_at",
            "edit_distance",
            "created_at",
        ]


class ThreadDetailSerializer(ThreadListSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    drafts = DraftSummarySerializer(many=True, read_only=True)

    class Meta(ThreadListSerializer.Meta):
        fields = [*ThreadListSerializer.Meta.fields, "messages", "drafts"]


class ReviewQueueSerializer(DraftSummarySerializer):
    thread = ThreadListSerializer(read_only=True)
    body_text = serializers.CharField(read_only=True)

    class Meta(DraftSummarySerializer.Meta):
        fields = [*DraftSummarySerializer.Meta.fields, "thread", "body_text"]


class DraftPatchSerializer(serializers.Serializer):
    body_text = serializers.CharField(max_length=20000)


class DraftRequestSerializer(serializers.Serializer):
    instruction = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class SnoozeSerializer(serializers.Serializer):
    until = serializers.DateTimeField()


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class FlagSerializer(serializers.Serializer):
    flag = serializers.ChoiceField(choices=[(f, f) for f in ALL_FLAGS])


class StyleGuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = StyleGuide
        fields = [
            "sign_off",
            "tone_rules",
            "banned_phrases",
            "must_include",
            "few_shot_examples",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_few_shot_examples(self, value: list) -> list:  # type: ignore[type-arg]
        if len(value) > MAX_FEW_SHOT_EXAMPLES:
            raise serializers.ValidationError(f"at most {MAX_FEW_SHOT_EXAMPLES} examples")
        for example in value:
            if not isinstance(example, dict) or "body" not in example:
                raise serializers.ValidationError("each example needs at least a 'body'")
        return value


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReplyTemplate
        fields = ["id", "intent", "name", "body", "created_at"]
        read_only_fields = ["id", "created_at"]


class ProviderSetupSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """One row of the OAuth setup checklist (§6.3): what is configured and what is missing."""

    provider = serializers.CharField()
    configured = serializers.BooleanField()
    redirect_uri = serializers.CharField(allow_blank=True)
    read_scopes = serializers.ListField(child=serializers.CharField())
    send_scope = serializers.CharField()
    missing_env = serializers.ListField(child=serializers.CharField())


class SetupStatusSerializer(serializers.Serializer):  # type: ignore[type-arg]
    providers = ProviderSetupSerializer(many=True)
    mailboxes = MailboxSerializer(many=True)
