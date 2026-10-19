from pathlib import Path

from manual_assistant.ui import AssistantService, build_app

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "samples" / "tx200_sample_manual.pdf"


def test_upload_then_ask_returns_cited_page():
    svc = AssistantService()
    assert "Upload" in svc.ask("E101").text
    assert "tx200_sample_manual.pdf" in svc.add_manuals([SAMPLE])
    answer = svc.ask("E101")
    assert answer.citations
    md = svc.page_markdown(answer.citations[0])
    assert answer.citations[0] in md and "E101" in md


def test_reupload_replaces_instead_of_duplicating():
    svc = AssistantService()
    svc.add_manuals([SAMPLE])
    n = len(svc.chunks)
    svc.add_manuals([SAMPLE])
    assert len(svc.chunks) == n and svc.manuals() == [SAMPLE.name]


def test_unknown_citation_and_bad_file(tmp_path):
    svc = AssistantService()
    bad = tmp_path / "empty.pdf"
    bad.write_bytes(b"")
    assert "No readable" in svc.add_manuals([bad])
    assert "Select a source" in svc.page_markdown("nope, p. 9")


def test_app_builds():
    assert build_app(AssistantService()) is not None
