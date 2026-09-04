"""Golden-file drafting tests (§6.5): recorded model replies in fixtures/drafts/*.json →
our guardrail pass produces exactly the expected flags. Includes THE injection fixture."""

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apps.invoices.factories import InvoiceFactory
from apps.mail.domain.text import IFSC_RE
from apps.mail.factories import MailboxFactory
from apps.mail.models import DraftStatus, EmailDraft, ReplyTemplate, StyleGuide, ThreadStatus
from apps.mail.providers import RawMessage
from apps.mail.services import drafting, llm
from apps.mail.services.sync import upsert_message
from apps.mail.tests.fakes import FakeAnthropic
from apps.parties.factories import PartyFactory
from apps.payments.factories import PaymentFactory

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "drafts"
ACCOUNT_NUMBER = re.compile(r"\d{9,18}")


def load(name: str) -> dict:  # type: ignore[type-arg]
    return json.loads((FIXTURES / f"{name}.json").read_text())


def seed(org, fx):  # type: ignore[no-untyped-def]
    """Party + invoices + mailbox + inbound message + (simulated) classification."""
    party = PartyFactory(org=org, kind="customer", **fx["party"])
    for inv in fx["invoices"]:
        InvoiceFactory(
            org=org,
            party=party,
            invoice_number=inv["invoice_number"],
            invoice_date=datetime.fromisoformat(inv["invoice_date"]).date(),
            due_date=datetime.fromisoformat(inv["due_date"]).date(),
            total=Decimal(inv["total"]),
            amount_paid=Decimal(inv["amount_paid"]),
            payment_status=inv["payment_status"],
            direction=inv["direction"],
            status=inv["status"],
            taxable_value=Decimal(inv["total"]) / Decimal("1.18"),
            cgst=Decimal("0"),
            sgst=Decimal("0"),
            igst=Decimal("0"),
        )
    mailbox = MailboxFactory(org=org)
    message = upsert_message(
        mailbox,
        RawMessage(
            provider_message_id=f"m-{fx['inbound']['subject'][:10]}",
            provider_thread_id="t-1",
            from_address=fx["inbound"]["from_address"],
            to=[mailbox.email_address],
            cc=[],
            date=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
            subject=fx["inbound"]["subject"],
            body_text=fx["inbound"]["body_text"],
            body_html="",
        ),
    )
    assert message is not None
    thread = message.thread
    thread.party = party
    thread.party_resolution = "primary_email"
    for k, v in fx["thread"].items():
        setattr(thread, k, v)
    thread.save()
    return thread, message


@pytest.mark.parametrize(
    "name", ["payment_delay_clean", "invented_invoice", "discount_agreed", "injection"]
)
def test_golden_draft_flags(org_a, name) -> None:  # type: ignore[no-untyped-def]
    fx = load(name)
    thread, inbound = seed(org_a.org, fx)
    fake = FakeAnthropic([fx["recorded_reply"]])
    draft = drafting.generate_draft(thread, actor=org_a.user, client=fake)
    assert draft.guardrail_flags == fx["expected_flags"]
    assert draft.status == DraftStatus.PENDING_REVIEW and draft.version == 1
    assert draft.in_reply_to == inbound and draft.prompt_version == "draft_reply_v1"
    assert draft.body_text == fx["recorded_reply"]["body_text"]
    thread.refresh_from_db()
    assert thread.status == ThreadStatus.DRAFTED
    # the model saw exactly what the snapshot recorded
    request = fake.calls[0]
    assert request["system"] == draft.context_snapshot["llm_request"]["system"]
    assert request["messages"] == draft.context_snapshot["llm_request"]["messages"]
    assert request["tool_choice"] == {"type": "tool", "name": "draft_reply"}
    assert request["tools"][0]["strict"] is True


def test_clean_draft_snapshot_has_exactly_the_customer_facts(org_a) -> None:  # type: ignore[no-untyped-def]
    fx = load("payment_delay_clean")
    thread, _ = seed(org_a.org, fx)
    PaymentFactory(org=org_a.org, party=thread.party, amount=Decimal("50000.00"))
    draft = drafting.generate_draft(thread, client=FakeAnthropic([fx["recorded_reply"]]))
    ctx = draft.context_snapshot["context"]
    assert [i["invoice_number"] for i in ctx["open_invoices"]] == ["INV-2026-0142", "INV-2026-0157"]
    assert ctx["aging"]["total_outstanding"] == "354000.00"
    assert ctx["recent_payments"][0]["amount"] == "50000.00"
    assert ctx["party"]["legal_name"] == "Bharat Precision Tools Pvt Ltd"
    allowed = draft.context_snapshot["allowed"]
    assert {"236000.00", "118000.00", "354000.00", "50000.00"} <= set(allowed["amounts"])
    assert "2026-08-15" in allowed["dates"] and "INV-2026-0142" in allowed["invoice_numbers"]
    assert draft.guardrail_flags == []


def test_injection_fixture_refuses_and_wraps_inbound(org_a) -> None:  # type: ignore[no-untyped-def]
    fx = load("injection")
    thread, inbound = seed(org_a.org, fx)
    assert inbound.injection_flag is True
    draft = drafting.generate_draft(thread, client=FakeAnthropic([fx["recorded_reply"]]))
    assert "injection_suspected" in draft.guardrail_flags
    assert not IFSC_RE.search(draft.body_text)
    assert not ACCOUNT_NUMBER.search(draft.body_text)
    assert "attacker@evil.com" not in draft.body_text
    snap = draft.context_snapshot
    assert snap["inbound_wrapped"].startswith("<untrusted_email>")
    assert snap["inbound_wrapped"].rstrip().endswith("</untrusted_email>")
    assert "ignore previous instructions" in snap["inbound_wrapped"]
    sent_to_model = snap["llm_request"]["messages"][0]["content"]
    assert "<untrusted_email>" in sent_to_model and "</untrusted_email>" in sent_to_model
    assert "never include bank details" in snap["llm_request"]["system"]
    assert snap["inbound_injection_flag"] is True


def test_regenerate_supersedes_prior_and_uses_style_guide(org_a) -> None:  # type: ignore[no-untyped-def]
    fx = load("payment_delay_clean")
    thread, _ = seed(org_a.org, fx)
    StyleGuide.objects.create(
        org=org_a.org,
        sign_off="Regards, Nexren",
        banned_phrases=["do the needful"],
        few_shot_examples=[
            {"intent": "dispute", "body": "d"},
            {"intent": "payment_delay_notice", "body": "p"},
        ],
    )
    ReplyTemplate.objects.create(
        org=org_a.org, intent="payment_delay_notice", name="Delay", body="T"
    )
    first = drafting.generate_draft(thread, client=FakeAnthropic([fx["recorded_reply"]]))
    second = drafting.generate_draft(
        thread, instruction="Be firmer.", client=FakeAnthropic([fx["recorded_reply"]])
    )
    first.refresh_from_db()
    assert first.status == DraftStatus.SUPERSEDED and second.version == 2
    assert second.instruction == "Be firmer."
    ctx = second.context_snapshot["context"]
    assert ctx["style_guide"]["sign_off"] == "Regards, Nexren"
    assert ctx["few_shot_examples"][0]["intent"] == "payment_delay_notice"  # matching first
    assert ctx["reply_template"]["name"] == "Delay"
    assert (
        "REVIEWER INSTRUCTION: Be firmer."
        in second.context_snapshot["llm_request"]["messages"][0]["content"]
    )


def test_unresolved_party_is_flagged_and_model_errors_surface(org_a) -> None:  # type: ignore[no-untyped-def]
    fx = load("payment_delay_clean")
    thread, _ = seed(org_a.org, fx)
    thread.party = None
    thread.save()
    draft = drafting.generate_draft(thread, client=FakeAnthropic([fx["recorded_reply"]]))
    assert "party_unresolved" in draft.guardrail_flags
    assert draft.context_snapshot["context"]["open_invoices"] == []
    with pytest.raises(drafting.DraftError):
        drafting.generate_draft(thread, client=FakeAnthropic([], stop_reason="refusal"))
    with pytest.raises(drafting.DraftError):
        drafting.generate_draft(thread, client=FakeAnthropic([{"body_text": ""}]))


def test_draft_api_endpoint(client_a, org_a, viewer_client, client_b, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fx = load("payment_delay_clean")
    thread, _ = seed(org_a.org, fx)
    monkeypatch.setattr(llm, "client", lambda: FakeAnthropic([fx["recorded_reply"]]))
    assert viewer_client.post(f"/api/mail/threads/{thread.pk}/draft/").status_code == 403
    assert client_b.post(f"/api/mail/threads/{thread.pk}/draft/").status_code == 404
    resp = client_a.post(f"/api/mail/threads/{thread.pk}/draft/", {"instruction": "short"})
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["guardrail_flags"] == [] and body["version"] == 1
    assert body["context_snapshot"]["instruction"] == "short"
    assert EmailDraft.objects.get(pk=body["id"]).created_by == org_a.user
    detail = client_a.get(f"/api/mail/threads/{thread.pk}/").json()
    assert detail["drafts"][0]["id"] == body["id"] and detail["status"] == "drafted"
    monkeypatch.setattr(llm, "client", lambda: FakeAnthropic([], stop_reason="refusal"))
    assert client_a.post(f"/api/mail/threads/{thread.pk}/draft/").status_code == 400


def test_llm_client_requires_key(settings) -> None:  # type: ignore[no-untyped-def]
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(llm.LLMError):
        llm.client()
    settings.ANTHROPIC_API_KEY = "k"
    assert llm.client() is not None


def test_text_to_html_escapes() -> None:
    assert drafting.text_to_html("a <b>\nc\n\nd") == "<p>a &lt;b&gt;<br>c</p><p>d</p>"
