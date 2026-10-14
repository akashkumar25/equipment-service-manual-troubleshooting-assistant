"""PDF ingestion: one chunk per page, enriched with model, system and fault codes.

Page-level chunks keep citations exact: every chunk carries the manual file name
and the 1-based PDF page number it came from.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field
from pypdf import PdfReader

# Fault codes such as E101, F-2040, SPN 100 FMI 3 (normalised below).
FAULT_ROW = re.compile(
    r"^\s*(?P<code>(?:SPN\s?\d{1,5}\s?FMI\s?\d{1,2})|(?:[A-Z]{1,3}-?\d{2,5}))\s{1,}(?P<desc>\S.*)$"
)
MODEL_LINE = re.compile(r"^\s*(?:Model|Machine)\s*:\s*(?P<v>\S.*)$", re.IGNORECASE)
SYSTEM_LINE = re.compile(r"^\s*(?:Section\s*[\d.]*\s*[:\-]?\s*|System\s*:\s*)(?P<v>\S.*)$", re.IGNORECASE)


class FaultEntry(BaseModel):
    code: str
    description: str


class PageChunk(BaseModel):
    manual: str
    page: int = Field(ge=1)
    text: str
    model: str | None = None
    system: str | None = None
    fault_codes: list[FaultEntry] = Field(default_factory=list)

    @property
    def citation(self) -> str:
        return f"{self.manual}, p. {self.page}"


def normalise_code(code: str) -> str:
    """Upper-case and collapse whitespace so 'spn 100 fmi 3' == 'SPN 100 FMI 3'."""
    return re.sub(r"\s+", " ", code.strip().upper())


def extract_fault_entries(text: str) -> list[FaultEntry]:
    entries: list[FaultEntry] = []
    for line in text.splitlines():
        m = FAULT_ROW.match(line)
        if m:
            entries.append(
                FaultEntry(code=normalise_code(m["code"]), description=m["desc"].strip())
            )
    return entries


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            return m["v"].strip()
    return None


def ingest_pdf(path: Path) -> list[PageChunk]:
    """Split a PDF into one PageChunk per non-empty page.

    Model and system are carried forward from the most recent page that declares
    them, because manuals usually state them once per section.
    """
    reader = PdfReader(str(path))
    chunks: list[PageChunk] = []
    model: str | None = None
    system: str | None = None
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        model = _first_match(MODEL_LINE, text) or model
        system = _first_match(SYSTEM_LINE, text) or system
        if not text:
            continue
        chunks.append(
            PageChunk(
                manual=path.name,
                page=number,
                text=text,
                model=model,
                system=system,
                fault_codes=extract_fault_entries(text),
            )
        )
    return chunks


def ingest_dir(directory: Path) -> list[PageChunk]:
    chunks: list[PageChunk] = []
    for pdf in sorted(directory.glob("*.pdf")):
        chunks.extend(ingest_pdf(pdf))
    return chunks


def save_chunks(chunks: list[PageChunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(c.model_dump_json() + "\n")


def load_chunks(path: Path) -> list[PageChunk]:
    with path.open(encoding="utf-8") as fh:
        return [PageChunk.model_validate(json.loads(line)) for line in fh if line.strip()]
