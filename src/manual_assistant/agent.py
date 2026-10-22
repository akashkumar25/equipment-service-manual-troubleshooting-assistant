"""Troubleshooting agent: fault-code tool results + retrieved pages -> cited answer.

Flow for each question:
1. Extract fault codes from the question and look them up exactly (tool call).
2. Retrieve the most relevant manual pages with hybrid search.
3. Ask the LLM to answer using only that evidence, citing ``[manual, p. N]``.

The LLM is any OpenAI-compatible chat endpoint (Ollama by default). If it is
unreachable the agent falls back to an extractive answer built from the same
evidence, so the tool still works fully offline.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Protocol

from pydantic import BaseModel, Field

from .config import Settings
from .i18n import LANGUAGE_NAMES, detect_language, expand_query, label
from .retrieval import Hit, HybridRetriever
from .tools import FaultCodeLookup, FaultMatch, find_codes

SYSTEM_PROMPT = (
    "You are a service technician's assistant. Answer ONLY from the evidence provided. "
    "Give numbered troubleshooting steps. After each claim cite its source as "
    "[manual, p. N] exactly as written in the evidence. If the evidence does not cover "
    "the question, say so instead of guessing. The evidence may be in another language than "
    "the question: translate it, but keep fault codes and the [manual, p. N] citations unchanged."
)


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class OpenAICompatibleLLM:
    """Minimal chat-completions client (stdlib only)."""

    def __init__(self, base_url: str, model: str, api_key: str = "", timeout: float = 120.0):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.api_key, self.timeout = model, api_key, timeout

    @classmethod
    def from_settings(cls, s: Settings) -> OpenAICompatibleLLM:
        return cls(s.llm_base_url, s.llm_model, s.llm_api_key)

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)["choices"][0]["message"]["content"].strip()


class Answer(BaseModel):
    question: str
    text: str
    citations: list[str] = Field(default_factory=list)
    fault_matches: list[FaultMatch] = Field(default_factory=list)
    used_llm: bool = False
    language: str = "en"


_CITATION = re.compile(r"\[([^\[\]]+?,\s*p\.\s*\d+)\]")


class TroubleshootingAgent:
    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLM | None = None,
        lookup: FaultCodeLookup | None = None,
        top_k: int = 3,
    ):
        self.retriever = retriever
        self.llm = llm
        self.lookup = lookup or FaultCodeLookup(retriever.chunks)
        self.top_k = top_k

    def _evidence(self, question: str, lang: str) -> tuple[list[FaultMatch], list[Hit]]:
        matches: list[FaultMatch] = []
        for code in find_codes(question):
            matches.extend(self.lookup.lookup(code))
        return matches, self.retriever.search(expand_query(question, lang), self.top_k)

    @staticmethod
    def _format_evidence(matches: list[FaultMatch], hits: list[Hit]) -> str:
        parts: list[str] = []
        if matches:
            parts.append("Fault code table entries:")
            parts += [f"- {m.code}: {m.description} [{m.citation}]" for m in matches]
        parts.append("Manual pages:")
        for h in hits:
            parts.append(f"[{h.citation}]\n{h.chunk.text}")
        return "\n".join(parts)

    def ask(self, question: str, language: str | None = None) -> Answer:
        """Answer in ``language`` (a code like "de"); detected from the question if omitted."""
        lang = language if language in LANGUAGE_NAMES else detect_language(question)
        matches, hits = self._evidence(question, lang)
        if not matches and not hits:
            return Answer(question=question, text=label(lang, "none"), language=lang)
        # Known sources, in priority order: exact table hits first, then retrieval.
        sources = list(dict.fromkeys([m.citation for m in matches] + [h.citation for h in hits]))
        if self.llm is not None:
            try:
                prompt = (
                    f"Question: {question}\n\nAnswer in {LANGUAGE_NAMES[lang]}.\n\n"
                    f"Evidence:\n{self._format_evidence(matches, hits)}"
                )
                text = self.llm.complete(SYSTEM_PROMPT, prompt)
                cited = [c for c in dict.fromkeys(_CITATION.findall(text)) if c in sources]
                return Answer(
                    question=question,
                    text=text,
                    citations=cited or sources,
                    fault_matches=matches,
                    used_llm=True,
                    language=lang,
                )
            except (urllib.error.URLError, OSError, KeyError, ValueError):
                pass  # fall through to the offline answer
        return Answer(
            question=question,
            text=self._extractive(matches, hits, lang),
            citations=sources,
            fault_matches=matches,
            language=lang,
        )

    @staticmethod
    def _extractive(matches: list[FaultMatch], hits: list[Hit], lang: str = "en") -> str:
        lines: list[str] = []
        for m in matches:
            lines.append(f"{m.code}: {m.description} [{m.citation}]")
        for h in hits:
            first = next((ln.strip() for ln in h.chunk.text.splitlines() if ln.strip()), "")
            lines.append(f"{label(lang, 'see')} [{h.citation}]: {first}")
        return "\n".join(lines)
