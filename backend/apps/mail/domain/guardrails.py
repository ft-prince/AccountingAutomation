"""Guardrail pass over a model-drafted reply. PROJECT_SPECS §6.5 — flag names are exact.
Pure: no Django, no I/O. Any flag blocks approve until a reviewer acknowledges it."""

import re
from dataclasses import dataclass, field

from apps.mail.domain.text import (
    IFSC_RE,
    date_forms,
    find_dates,
    find_invoice_numbers,
    find_money,
)

PROMISES_DISCOUNT_OR_WAIVER = "promises_discount_or_waiver"
COMMITS_TO_DATE_OR_DELIVERY = "commits_to_date_or_delivery"
QUOTES_A_PRICE = "quotes_a_price"
LEGAL_LANGUAGE = "legal_language"
CONTAINS_BANK_DETAILS = "contains_bank_details"
REFERENCES_INVOICE_NOT_IN_DB = "references_invoice_not_in_db"
AMOUNT_MISMATCH_WITH_DB = "amount_mismatch_with_db"
INJECTION_SUSPECTED = "injection_suspected"
PARTY_UNRESOLVED = "party_unresolved"
OUTSIDE_BUSINESS_SCOPE = "outside_business_scope"
SENTIMENT_ESCALATION = "sentiment_escalation"

ALL_FLAGS: tuple[str, ...] = (
    PROMISES_DISCOUNT_OR_WAIVER,
    COMMITS_TO_DATE_OR_DELIVERY,
    QUOTES_A_PRICE,
    LEGAL_LANGUAGE,
    CONTAINS_BANK_DETAILS,
    REFERENCES_INVOICE_NOT_IN_DB,
    AMOUNT_MISMATCH_WITH_DB,
    INJECTION_SUSPECTED,
    PARTY_UNRESOLVED,
    OUTSIDE_BUSINESS_SCOPE,
    SENTIMENT_ESCALATION,
)

NEGATIVE = "negative"

DISCOUNT_TERMS = re.compile(
    r"\b(discount|waive|waiver|waived|write[- ]?off|credit note|rebate|concession)\b", re.I
)
AGREEING = re.compile(
    r"\b(offer|offering|provide|providing|give|giving|extend|extending|apply|applying|"
    r"approve[ds]?|agree[ds]?|agreeing|happy|glad|pleased|willing|able|will|can|shall|"
    r"issue|issuing|honou?r|grant|granting|confirm)\b",
    re.I,
)
NEGATION = re.compile(
    r"\b(not|no|cannot|can't|unable|won't|don't|doesn't|isn't|never|unfortunately|"
    r"regret|decline|refrain)\b",
    re.I,
)
DELIVERY_COMMITMENT = re.compile(
    r"\b(will|shall|can|would)\s+(be\s+)?(deliver|dispatch|ship|complete|release|process|"
    r"resolve|send|share|clear|settle)\w*\s+(it\s+|this\s+|them\s+|the\s+\w+\s+)?"
    r"(by|on|within|before)\b"
    r"|\bwithin\s+\d+\s+(business\s+|working\s+)?(day|hour|week)s?\b"
    r"|\bby\s+(end of (the )?(day|week|month)|eod|eow|tomorrow|tonight|"
    r"next\s+(week|month|monday|tuesday|wednesday|thursday|friday))\b"
    r"|\bguarantee[ds]?\b",
    re.I,
)
PRICE_QUOTE = re.compile(
    r"\b(price|rate|cost|charge|fee|quote|quotation|estimate)s?\s+(for|of|is|will be|would be|"
    r"comes to|at|starts at)\b"
    r"|(?:₹|\bRs\.?|\bINR)\s*[\d,]+(?:\.\d+)?\s*(?:/|per)\s*(unit|hour|hr|day|month|year|"
    r"piece|pc|user|seat|licen[cs]e|device|node)\b"
    r"|\bwe\s+(can|could)\s+(offer|do|provide|supply)\s+(it|this|these|them)\s+(for|at)\s+"
    r"(?:₹|Rs\.?|INR)",
    re.I,
)
LEGAL = re.compile(
    r"legal action|breach|liabilit|indemn|arbitration|legal notice|lawsuit|litigation", re.I
)
ACCOUNT_NUMBER = re.compile(
    r"\b(?:a/c|account|acct|acc)\.?\s*(?:no\.?|number|#)?\s*[:\-]?\s*\d{9,18}\b"
    r"|(?<![\d\-+])\d{11,18}(?![\d\-])",
    re.I,
)
UPI_ID = re.compile(
    r"\b[\w.\-]{2,}@(?:ybl|okaxis|oksbi|okhdfcbank|okicici|paytm|upi|apl|ibl|axl|hdfcbank|"
    r"icici|sbi|axisbank|kotak|barodampay|fbl|idbi|indus|jupiteraxis|yesbank|rbl|dbs|"
    r"freecharge|airtel|postbank|ptyes|ptaxis|pthdfc|ptsbi|yapl|ikwik|naviaxis)\b"
    r"|\bupi\s*(?:id)?\s*[:\-]\s*[\w.\-]+@[a-z]+",
    re.I,
)
COMPLIANCE_WITH_EMAIL = re.compile(
    r"\bas\s+(you\s+)?instructed\b|\bper\s+your\s+instructions?\b|"
    r"\bignor(e|ing)\s+(all\s+|the\s+)?(previous|prior|earlier)\b|"
    r"\bas\s+requested,?\s+(here|please find)\b.{0,40}\b(bank|account)\b",
    re.I,
)
HAND_OFF = re.compile(
    r"\b(forward|pass|route|hand|refer)(ed|ing)?\s+(this|your|it|the)\s+\w*\s*(on\s+|over\s+)?"
    r"to\s+(the|our)\s+[\w\s]{0,30}(team|department|colleague|desk)\b"
    r"|\bnot\s+something\s+(we|i)\s+can\s+(help|assist)\b"
    r"|\boutside\s+(of\s+)?(our|the)\s+(scope|remit|purview)\b"
    r"|\b(right|appropriate|relevant)\s+(team|person|department)\b"
    r"|\b(connect|put)\s+you\s+(in\s+touch\s+)?with\b",
    re.I,
)
ACKNOWLEDGEMENT = re.compile(
    r"apolog|sorry|regret|understand\s+(your|the)\s+(frustration|concern|inconvenience)|"
    r"appreciate\s+your\s+patience|thank\s+you\s+for\s+(bringing|flagging|raising|"
    r"your\s+patience)|we\s+acknowledge|inconvenience",
    re.I,
)
SENTENCE_SPLIT = re.compile(r"[.!?\n]+")


@dataclass(frozen=True)
class Snapshot:
    """The facts the model was given — the only amounts, invoices and dates a draft may use."""

    amounts: frozenset[str] = frozenset()  # normalised '11800.00'
    invoice_numbers: frozenset[str] = frozenset()  # normalised 'INV-0042'
    dates: frozenset[str] = frozenset()  # ISO 'YYYY-MM-DD'
    party_resolved: bool = False
    inbound_sentiment: str = ""
    inbound_injection_flag: bool = False
    self_reported_flags: tuple[str, ...] = field(default_factory=tuple)


def _promises_discount(text: str) -> bool:
    for sentence in SENTENCE_SPLIT.split(text):
        if not DISCOUNT_TERMS.search(sentence):
            continue
        if NEGATION.search(sentence):
            continue
        if AGREEING.search(sentence):
            return True
    return False


def _commits_to_date(text: str, snapshot: Snapshot) -> bool:
    if DELIVERY_COMMITMENT.search(text):
        return True
    allowed = date_forms(set(snapshot.dates))
    return bool(find_dates(text) - allowed)


def _contains_bank_details(text: str) -> bool:
    return bool(IFSC_RE.search(text) or ACCOUNT_NUMBER.search(text) or UPI_ID.search(text))


def _injection_suspected(text: str, snapshot: Snapshot, has_bank_details: bool) -> bool:
    if snapshot.inbound_injection_flag or has_bank_details:
        return True
    return bool(COMPLIANCE_WITH_EMAIL.search(text))


def _outside_scope(text: str, snapshot: Snapshot) -> bool:
    if OUTSIDE_BUSINESS_SCOPE in snapshot.self_reported_flags:
        return True
    return bool(HAND_OFF.search(text))


def _sentiment_escalation(text: str, snapshot: Snapshot) -> bool:
    if snapshot.inbound_sentiment != NEGATIVE:
        return False
    return not ACKNOWLEDGEMENT.search(text)


def check(draft_text: str, snapshot: Snapshot) -> list[str]:
    """Return the §6.5 flags raised by `draft_text`, in canonical order, without duplicates."""
    has_bank_details = _contains_bank_details(draft_text)
    raised: set[str] = {f for f in snapshot.self_reported_flags if f in ALL_FLAGS}
    if _promises_discount(draft_text):
        raised.add(PROMISES_DISCOUNT_OR_WAIVER)
    if _commits_to_date(draft_text, snapshot):
        raised.add(COMMITS_TO_DATE_OR_DELIVERY)
    if PRICE_QUOTE.search(draft_text):
        raised.add(QUOTES_A_PRICE)
    if LEGAL.search(draft_text):
        raised.add(LEGAL_LANGUAGE)
    if has_bank_details:
        raised.add(CONTAINS_BANK_DETAILS)
    if find_invoice_numbers(draft_text) - set(snapshot.invoice_numbers):
        raised.add(REFERENCES_INVOICE_NOT_IN_DB)
    if find_money(draft_text) - set(snapshot.amounts):
        raised.add(AMOUNT_MISMATCH_WITH_DB)
    if _injection_suspected(draft_text, snapshot, has_bank_details):
        raised.add(INJECTION_SUSPECTED)
    if not snapshot.party_resolved:
        raised.add(PARTY_UNRESOLVED)
    if _outside_scope(draft_text, snapshot):
        raised.add(OUTSIDE_BUSINESS_SCOPE)
    if _sentiment_escalation(draft_text, snapshot):
        raised.add(SENTIMENT_ESCALATION)
    return [f for f in ALL_FLAGS if f in raised]


def unacknowledged(flags: list[str], acknowledged: list[str]) -> list[str]:
    """guardrail_flags − acknowledged_flags; approve is refused while non-empty (§6.2)."""
    done = set(acknowledged)
    return [f for f in flags if f not in done]
