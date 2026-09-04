"""Heuristic prompt-injection pre-screen for inbound mail. CLAUDE.md §4: email text is DATA.
Pure. A hit sets EmailMessage.injection_flag; the model is never asked to decide this."""

import re

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(all\s+|the\s+)?(previous|prior)\s+instructions", re.I),
    ),
    (
        "ignore_rules",
        re.compile(r"ignore\s+(all\s+|the\s+|your\s+)?(rules|guidelines|policies)", re.I),
    ),
    ("you_are_an_ai", re.compile(r"\byou\s+are\s+an?\s+ai\b", re.I)),
    ("system_prompt", re.compile(r"\bsystem\s+prompt\b", re.I)),
    (
        "send_bank_details",
        re.compile(r"\bsend\b.{0,60}\bbank\s+(details|account|information)", re.I),
    ),
    ("forward_to", re.compile(r"\bforward\b.{0,60}\bto\b", re.I)),
    ("disregard", re.compile(r"\bdisregard\b", re.I)),
)
MAX_NOTE_LENGTH = 500


def screen(text: str) -> str | None:
    """Return a short note naming the matched heuristics, or None when the text looks clean."""
    hits = [name for name, pattern in PATTERNS if pattern.search(text)]
    if not hits:
        return None
    return f"injection heuristics matched: {', '.join(hits)}"[:MAX_NOTE_LENGTH]
