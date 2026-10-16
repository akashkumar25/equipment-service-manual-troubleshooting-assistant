"""Fault-code lookup tool over ingested manual pages."""

from __future__ import annotations

import re

from pydantic import BaseModel

from .ingest import PageChunk, normalise_code

# Same code shapes as ingestion: E101, F-2040, SPN 100 FMI 3.
CODE_IN_TEXT = re.compile(
    r"\b(?:SPN\s?\d{1,5}\s?FMI\s?\d{1,2}|[A-Z]{1,3}-?\d{2,5})\b", re.IGNORECASE
)


class FaultMatch(BaseModel):
    code: str
    description: str
    manual: str
    page: int
    model: str | None = None
    system: str | None = None

    @property
    def citation(self) -> str:
        return f"{self.manual}, p. {self.page}"


def find_codes(text: str) -> list[str]:
    """Return normalised fault codes mentioned in free text, in order, deduplicated.

    Only tokens containing a digit are considered, so words like "an" never match.
    """
    seen: list[str] = []
    for m in CODE_IN_TEXT.finditer(text):
        if not any(ch.isdigit() for ch in m.group()):
            continue
        code = normalise_code(m.group())
        if code not in seen:
            seen.append(code)
    return seen


class FaultCodeLookup:
    """Exact fault-code lookup from the tables captured at ingestion time."""

    def __init__(self, chunks: list[PageChunk]):
        self._by_code: dict[str, list[FaultMatch]] = {}
        for c in chunks:
            for entry in c.fault_codes:
                self._by_code.setdefault(self._key(entry.code), []).append(
                    FaultMatch(
                        code=entry.code,
                        description=entry.description,
                        manual=c.manual,
                        page=c.page,
                        model=c.model,
                        system=c.system,
                    )
                )

    @staticmethod
    def _key(code: str) -> str:
        # 'F-2040' and 'F2040' are the same code.
        return normalise_code(code).replace("-", "")

    def lookup(self, code: str, model: str | None = None) -> list[FaultMatch]:
        matches = self._by_code.get(self._key(code), [])
        if model:
            wanted = model.lower()
            matches = [m for m in matches if m.model and wanted in m.model.lower()]
        return list(matches)
