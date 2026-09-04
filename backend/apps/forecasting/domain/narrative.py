"""Narrative guardrail (PROJECT_SPECS §8.8): the model may restate numbers, never produce them.
Pure: no Django, no I/O."""

import re
from dataclasses import dataclass

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    """Every numeric token, normalised (commas stripped, trailing .0 kept as written)."""
    return {m.group(0).replace(",", "") for m in _NUMBER.finditer(text)}


@dataclass(frozen=True)
class NarrativeCheck:
    accepted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]  # (bullet, offending number)

    @property
    def ok(self) -> bool:
        return not self.rejected and len(self.accepted) == 5


def check_bullets(bullets: list[str], allowed_numbers: set[str]) -> NarrativeCheck:
    """Reject any bullet containing a number that is not present in the inputs."""
    allowed = {n.replace(",", "") for n in allowed_numbers}
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    for b in bullets[:5]:
        bad = next((n for n in sorted(numbers_in(b)) if n not in allowed), None)
        if bad is None:
            accepted.append(b.strip())
        else:
            rejected.append((b.strip(), bad))
    return NarrativeCheck(tuple(accepted), tuple(rejected))
