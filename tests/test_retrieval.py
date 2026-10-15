from pathlib import Path

import numpy as np
import pytest

from manual_assistant.cli import main
from manual_assistant.ingest import PageChunk, ingest_pdf
from manual_assistant.retrieval import BM25, HashingEmbedder, HybridRetriever, tokenize

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "samples" / "tx200_sample_manual.pdf"


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever(ingest_pdf(SAMPLE))


def test_tokenize_keeps_fault_codes_whole():
    assert tokenize("Code E101 and F-2040, Öl!") == ["code", "e101", "and", "f-2040", "öl"]


def test_bm25_prefers_matching_document():
    bm = BM25([tokenize("hydraulic oil hot"), tokenize("engine coolant leak")])
    s = bm.scores(tokenize("coolant"))
    assert s[1] > s[0] == 0


def test_hashing_embedder_similar_words_closer():
    e = HashingEmbedder()
    v = e.encode(["hydraulic", "hydraulics", "battery"])
    assert v[0] @ v[1] > v[0] @ v[2]
    assert np.isclose(np.linalg.norm(v[0]), 1.0)


def test_fault_code_query_cites_correct_page(retriever):
    hits = retriever.search("E101")
    pages = [h.chunk.page for h in hits[:2]]
    assert 3 in pages  # the E101 troubleshooting procedure
    assert "E101" in hits[0].chunk.text
    assert hits[0].citation == f"{SAMPLE.name}, p. {hits[0].chunk.page}"


def test_symptom_query_finds_engine_page(retriever):
    hits = retriever.search("engine overheating coolant", top_k=2)
    assert hits and hits[0].chunk.system == "Engine"
    assert hits[0].bm25_rank is not None


def test_empty_inputs():
    assert HybridRetriever([]).search("x") == []
    r = HybridRetriever([PageChunk(manual="m.pdf", page=1, text="abc")])
    assert r.search("   ") == []


def test_cli_search(tmp_path, capsys):
    idx = tmp_path / "c.jsonl"
    main(["ingest", "--manuals-dir", str(SAMPLE.parent), "--out", str(idx)])
    assert main(["search", "E101", "--index", str(idx)]) == 0
    assert "tx200_sample_manual.pdf, p." in capsys.readouterr().out
