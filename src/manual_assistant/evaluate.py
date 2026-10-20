"""Evaluate retrieval and citations on a labelled question set (JSONL).

Each line: ``{"question", "kind", "manual", "pages": [accepted pages], "keywords": [...]}``.
Metrics, per question kind and overall:

- top-1 / top-3 citation: an accepted page of the expected manual is the first /
  among the first three retrieved pages.
- agent citation: the agent's final citations include an accepted page.
- answer support: a keyword appears in the answer text or in a cited page.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from .agent import TroubleshootingAgent
from .ingest import PageChunk


class EvalQuestion(BaseModel):
    question: str
    kind: str
    manual: str
    pages: list[int]
    keywords: list[str]


def load_questions(path: Path) -> list[EvalQuestion]:
    with path.open(encoding="utf-8") as fh:
        return [EvalQuestion.model_validate(json.loads(ln)) for ln in fh if ln.strip()]


def _cited(citation: str, q: EvalQuestion) -> bool:
    manual, _, page = citation.rpartition(", p. ")
    return manual == q.manual and page.isdigit() and int(page) in q.pages


def evaluate(
    agent: TroubleshootingAgent, questions: list[EvalQuestion], chunks: list[PageChunk]
) -> dict[str, dict[str, float]]:
    """Return {kind or 'overall': {metric: value, 'n': count}}."""
    text_of = {c.citation: c.text.lower() for c in chunks}
    rows: dict[str, list[dict[str, bool]]] = defaultdict(list)
    for q in questions:
        hits = agent.retriever.search(q.question, 3)
        answer = agent.ask(q.question)
        support_text = answer.text.lower() + " ".join(text_of.get(c, "") for c in answer.citations)
        row = {
            "top1": bool(hits) and _cited(hits[0].citation, q),
            "top3": any(_cited(h.citation, q) for h in hits),
            "agent_citation": any(_cited(c, q) for c in answer.citations),
            "answer_support": any(k.lower() in support_text for k in q.keywords),
        }
        rows[q.kind].append(row)
        rows["overall"].append(row)
    report: dict[str, dict[str, float]] = {}
    for kind, rs in rows.items():
        report[kind] = {m: sum(r[m] for r in rs) / len(rs) for m in rs[0]} | {"n": len(rs)}
    return report


def to_markdown(report: dict[str, dict[str, float]]) -> str:
    head = "| question kind | n | top-1 citation | top-3 citation | agent citation | answer support |"
    lines = [head, "|---|---|---|---|---|---|"]
    for kind in [k for k in report if k != "overall"] + ["overall"]:
        r = report[kind]
        lines.append(
            f"| {kind} | {int(r['n'])} | {r['top1']:.0%} | {r['top3']:.0%} "
            f"| {r['agent_citation']:.0%} | {r['answer_support']:.0%} |"
        )
    return "\n".join(lines)
