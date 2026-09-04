from datetime import UTC, datetime

import factory

from apps.accounts.factories import OrganizationFactory
from apps.mail.models import EmailDraft, EmailMessage, EmailThread, MailboxConnection
from apps.mail.providers.gmail import READ_SCOPES


def _tokens() -> str:
    from apps.mail.crypto import encrypt_tokens

    return encrypt_tokens({"token": "access-token-secret", "refresh_token": "refresh-token-secret"})


class MailboxFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MailboxConnection

    org = factory.SubFactory(OrganizationFactory)
    provider = "gmail"
    email_address = factory.Sequence(lambda n: f"accounts{n}@nexren.example")
    encrypted_tokens = factory.LazyFunction(_tokens)
    scopes = factory.LazyFunction(lambda: list(READ_SCOPES))


class ThreadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailThread

    org = factory.SubFactory(OrganizationFactory)
    mailbox = factory.LazyAttribute(lambda o: MailboxFactory(org=o.org))
    provider_thread_id = factory.Sequence(lambda n: f"thread-{n}")
    subject = factory.Sequence(lambda n: f"Subject {n}")
    last_inbound_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    sla_due_at = datetime(2026, 9, 2, 9, 0, tzinfo=UTC)


class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailMessage

    org = factory.LazyAttribute(lambda o: o.thread.org)
    thread = factory.SubFactory(ThreadFactory)
    mailbox = factory.LazyAttribute(lambda o: o.thread.mailbox)
    provider_message_id = factory.Sequence(lambda n: f"msg-{n}")
    direction = "inbound"
    from_address = "buyer@customer.example"
    to_addresses = factory.LazyAttribute(lambda o: [o.mailbox.email_address])
    date = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    subject = "Payment update"
    body_text = "Hello, we will pay next week."


class DraftFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailDraft

    org = factory.LazyAttribute(lambda o: o.thread.org)
    thread = factory.SubFactory(ThreadFactory)
    version = factory.Sequence(lambda n: n + 1)
    prompt_version = "draft_reply_v1"
    model_name = "test-model"
    body_text = "Dear Sir,\n\nThank you for your email.\n\nRegards"
    context_snapshot = factory.LazyFunction(
        lambda: {
            "allowed": {"amounts": [], "invoice_numbers": [], "dates": []},
            "party_resolved": True,
            "inbound_sentiment": "neutral",
            "inbound_injection_flag": False,
        }
    )
