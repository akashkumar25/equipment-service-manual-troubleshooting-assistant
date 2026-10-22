"""Gradio UI: upload manuals, ask a question, inspect the cited pages.

The logic lives in :class:`AssistantService` (no Gradio import) so it can be
tested headless; :func:`build_app` only wires it to widgets.
"""

from __future__ import annotations

from pathlib import Path

from pypdf.errors import PdfReadError

from .agent import LLM, Answer, TroubleshootingAgent
from .i18n import LANGUAGE_NAMES
from .ingest import PageChunk, ingest_pdf
from .retrieval import HybridRetriever


class AssistantService:
    def __init__(self, chunks: list[PageChunk] | None = None, llm: LLM | None = None):
        self.llm = llm
        self.chunks: list[PageChunk] = list(chunks or [])
        self._agent: TroubleshootingAgent | None = None

    def add_manuals(self, paths: list[Path]) -> str:
        """Ingest uploaded PDFs, replacing pages of manuals with the same name."""
        added: list[str] = []
        for path in paths:
            try:
                new = ingest_pdf(Path(path))
            except (PdfReadError, OSError):
                continue
            if not new:
                continue
            self.chunks = [c for c in self.chunks if c.manual != new[0].manual] + new
            added.append(f"{new[0].manual} ({len(new)} pages)")
        self._agent = None
        if not added:
            return "No readable pages found in the uploaded files."
        return "Indexed: " + ", ".join(added)

    def manuals(self) -> list[str]:
        return sorted({c.manual for c in self.chunks})

    def ask(self, question: str, language: str | None = None) -> Answer:
        if not self.chunks:
            return Answer(question=question, text="Upload or load a manual first.")
        if self._agent is None:
            self._agent = TroubleshootingAgent(HybridRetriever(self.chunks), self.llm)
        return self._agent.ask(question, language)

    def page(self, citation: str) -> PageChunk | None:
        """Resolve a ``"manual.pdf, p. 3"`` citation to its page chunk."""
        for c in self.chunks:
            if c.citation == citation:
                return c
        return None

    def page_markdown(self, citation: str | None) -> str:
        chunk = self.page(citation) if citation else None
        if chunk is None:
            return "_Select a source to see the manual page._"
        meta = " | ".join(
            f"{k}: {v}" for k, v in (("model", chunk.model), ("system", chunk.system)) if v
        )
        header = f"**{chunk.citation}**" + (f"  \n{meta}" if meta else "")
        return f"{header}\n\n```text\n{chunk.text}\n```"


def build_app(service: AssistantService):
    import gradio as gr

    def upload(files):
        paths = [Path(f if isinstance(f, str) else f.name) for f in files or []]
        return service.add_manuals(paths), "\n".join(service.manuals())

    def ask(question, language):
        answer = service.ask(question, None if language == "auto" else language)
        first = answer.citations[0] if answer.citations else None
        return (
            answer.text,
            gr.update(choices=answer.citations, value=first),
            service.page_markdown(first),
        )

    with gr.Blocks(title="Service manual troubleshooting assistant") as app:
        gr.Markdown("# Service manual troubleshooting assistant")
        with gr.Row():
            with gr.Column(scale=1):
                files = gr.File(label="Manuals (PDF)", file_types=[".pdf"], file_count="multiple")
                status = gr.Markdown()
                loaded = gr.Textbox(label="Loaded manuals", value="\n".join(service.manuals()),
                                    interactive=False, lines=3)
            with gr.Column(scale=2):
                question = gr.Textbox(label="Fault code or symptom", placeholder="E101")
                language = gr.Dropdown(["auto", *LANGUAGE_NAMES], value="auto",
                                       label="Answer language")
                go = gr.Button("Ask", variant="primary")
                answer = gr.Textbox(label="Answer", lines=10, interactive=False)
                sources = gr.Radio(label="Sources (click to open the page)", choices=[])
                page = gr.Markdown(service.page_markdown(None))
        files.upload(upload, files, [status, loaded])
        go.click(ask, [question, language], [answer, sources, page])
        question.submit(ask, [question, language], [answer, sources, page])
        sources.change(service.page_markdown, sources, page)
    return app
