"""Per-line categories on ingest, and the optional (never required) model pass."""

import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from django.conf import settings
from django.core.management import call_command

from apps.accounts.factories import GSTINProfileFactory
from apps.documents.factories import DocumentFactory
from apps.documents.models import ExtractionRun
from apps.documents.tests.fakes import FakeAnthropic
from apps.invoices.services import LineInput, categorise_lines, ingest_extraction
from apps.parties.factories import CategoryFactory, PartyFactory
from apps.parties.models import ExpenseCategory

FIXTURES = Path(settings.BASE_DIR) / "tests" / "fixtures" / "invoices"
NEXREN_GSTIN = "27AAGFF2194N1ZZ"
D = Decimal


def _line(description: str, hsn_sac: str = "") -> LineInput:
    return LineInput(
        description=description,
        hsn_sac=hsn_sac,
        quantity=D("1"),
        uom="nos",
        unit_price=D("100.00"),
        discount=D("0"),
        rate=D("18"),
        cess_rate=D("0"),
        extracted={},
    )


def _stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """apps.core.llm is owned by another slice; stub its documented interface."""

    class LLMError(Exception):
        pass

    @dataclass(frozen=True)
    class ToolReply:
        tool_input: dict[str, Any] | None
        stop_reason: str
        input_tokens: int
        output_tokens: int
        model: str

    def call_tool(
        *,
        system: str,
        messages: list[dict[str, Any]],
        tool: dict[str, Any],
        max_tokens: int = 4000,
        client: Any | None = None,
    ) -> ToolReply:
        if client is None:
            raise LLMError("no client configured")
        resp = client.messages.create(
            model="m", max_tokens=max_tokens, system=system, messages=messages, tools=[tool]
        )
        block = resp.content[0]
        return ToolReply(
            tool_input=block.input if block.type == "tool_use" else None,
            stop_reason=resp.stop_reason,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model="m",
        )

    module = ModuleType("apps.core.llm")
    module.LLMError = LLMError  # type: ignore[attr-defined]
    module.ToolReply = ToolReply  # type: ignore[attr-defined]
    module.call_tool = call_tool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "apps.core.llm", module)


# --- rules only (no LLM anywhere) ------------------------------------------


def test_rules_only_when_the_llm_module_is_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setitem(sys.modules, "apps.core.llm", None)
    got = categorise_lines([_line("Zzz item 991")], None, client=FakeAnthropic([]))
    assert got[0].name == "Other" and got[0].confidence == D("0.20")


def test_strong_rule_hits_never_reach_the_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _stub_llm(monkeypatch)
    client = FakeAnthropic([{"lines": [{"index": 0, "category": "Marketing"}]}])
    got = categorise_lines([_line("Cloud compute Sep-25", "998315")], None, client=client)
    assert got[0].name == "Software & SaaS" and client.calls == []


# --- optional LLM pass, fully guarded --------------------------------------


def test_model_may_only_pick_names_from_the_seeded_list(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _stub_llm(monkeypatch)
    client = FakeAnthropic(
        [
            {
                "lines": [
                    {"index": 0, "category": "Marketing"},
                    {"index": 1, "category": "Crypto Mining"},  # not seeded → dropped
                    {"index": 2, "category": "Rent"},  # index the rules resolved → dropped
                    "junk",
                ]
            }
        ]
    )
    lines = [_line("Zzz 1"), _line("Zzz 2"), _line("Team lunch", "996333")]
    got = categorise_lines(lines, None, client=client)
    assert got[0].name == "Marketing" and got[0].confidence == D("0.60")
    assert got[1].name == "Other"  # invented name discarded
    assert got[2].name == "Meals & Entertainment"  # rules win, model ignored
    assert len(client.calls) == 1
    sent = json.loads(client.calls[0]["messages"][0]["content"])
    assert [ln["index"] for ln in sent["lines"]] == [0, 1]
    assert client.calls[0]["tools"][0]["name"] == "assign_expense_categories"


def test_model_refusal_or_garbage_keeps_the_rules_answer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _stub_llm(monkeypatch)
    assert categorise_lines([_line("Zzz")], None, client=FakeAnthropic([None]))[0].name == "Other"
    bad = FakeAnthropic([{"lines": "not a list"}])
    assert categorise_lines([_line("Zzz")], None, client=bad)[0].name == "Other"


def test_no_client_and_no_key_means_no_call(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _stub_llm(monkeypatch)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "", raising=False)
    assert categorise_lines([_line("Zzz")], "Rent")[0].name == "Rent"


def test_llm_error_is_logged_not_raised(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _stub_llm(monkeypatch)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key", raising=False)
    # client=None inside the stub raises LLMError; the rules answer survives.
    assert categorise_lines([_line("Zzz")], None)[0].name == "Other"


# --- wiring into ingest ------------------------------------------------------


@pytest.mark.django_db
def test_ingest_gives_each_line_its_own_category(org_a) -> None:  # type: ignore[no-untyped-def]
    call_command("seed_categories", verbosity=0)
    GSTINProfileFactory(org=org_a.org, gstin=NEXREN_GSTIN, state_code="27", is_default=True)
    parsed = json.loads((FIXTURES / "bharat_inter_mismatch.reply.json").read_text())
    run = ExtractionRun.objects.create(
        document=DocumentFactory(org=org_a.org),
        model_name="m",
        prompt_version="v1",
        parsed=parsed,
        field_confidence=parsed.get("field_confidence", {}),
    )
    inv = ingest_extraction(run)
    line = inv.lines.get(line_no=1)
    assert line.description == "Cloud compute Sep-25" and line.hsn_sac == "998315"
    assert line.category is not None and line.category.name == "Software & SaaS"
    assert line.category.org_id is None  # the system row
    assert line.confidence == D("0.900")  # from the rule, no per-line extraction confidence


@pytest.mark.django_db
def test_the_orgs_own_category_row_wins_over_the_system_row(org_a) -> None:  # type: ignore[no-untyped-def]
    call_command("seed_categories", verbosity=0)
    org = org_a.org
    mine = CategoryFactory(org=org, name="Software & SaaS")
    GSTINProfileFactory(org=org, gstin=NEXREN_GSTIN, state_code="27", is_default=True)
    parsed = json.loads((FIXTURES / "bharat_inter_mismatch.reply.json").read_text())
    run = ExtractionRun.objects.create(
        document=DocumentFactory(org=org),
        model_name="m",
        prompt_version="v1",
        parsed=parsed,
        field_confidence={},
    )
    inv = ingest_extraction(run)
    assert ExpenseCategory.objects.filter(name="Software & SaaS", org__isnull=True).exists()
    assert inv.lines.get(line_no=1).category_id == mine.pk


@pytest.mark.django_db
def test_unmatched_line_falls_back_to_the_party_default_row(org_a) -> None:  # type: ignore[no-untyped-def]
    from apps.invoices.factories import InvoiceFactory
    from apps.invoices.services import apply_edit

    default = CategoryFactory(org=org_a.org, name="Vendor default")
    meals = CategoryFactory(org=org_a.org, name="Meals & Entertainment", itc_eligible=False)
    party = PartyFactory(org=org_a.org, default_category=default)
    inv = InvoiceFactory(org=org_a.org, party=party)
    apply_edit(
        inv,
        {},
        [
            {"description": "Zzz item", "hsn_sac": "0000", "unit_price": "100", "rate": "18"},
            {"description": "Team lunch", "hsn_sac": "996333", "unit_price": "50", "rate": "5"},
        ],
        actor=org_a.user,
    )
    lines = list(inv.lines.order_by("line_no"))
    assert lines[0].category_id == default.pk  # nothing matched → party default
    assert lines[0].confidence == D("0.500")
    # 996333 → Meals & Entertainment: the org's own row, ITC blocked (§3.7).
    assert lines[1].category_id == meals.pk and lines[1].category.itc_eligible is False
    assert lines[1].confidence == D("0.900")
