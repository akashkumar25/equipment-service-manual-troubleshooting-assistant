from pathlib import Path

import pytest

from manual_assistant.cli import main
from manual_assistant.ingest import (
    extract_fault_entries,
    ingest_dir,
    ingest_pdf,
    load_chunks,
    normalise_code,
    save_chunks,
)

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "samples" / "tx200_sample_manual.pdf"


@pytest.fixture(scope="module")
def chunks():
    return ingest_pdf(SAMPLE)


def test_one_chunk_per_page_with_page_numbers(chunks):
    assert [c.page for c in chunks] == [1, 2, 3, 4]
    assert all(c.manual == SAMPLE.name for c in chunks)
    assert chunks[1].citation == "tx200_sample_manual.pdf, p. 2"


def test_model_and_system_metadata_carried_forward(chunks):
    assert chunks[1].model == "TX-200 Hydraulic Excavator"
    assert chunks[2].model == "TX-200 Hydraulic Excavator"  # not repeated on page 3
    assert chunks[1].system == "Hydraulic System"
    assert chunks[3].system == "Engine"


def test_fault_code_table_extracted(chunks):
    codes = {e.code: e.description for e in chunks[1].fault_codes}
    assert codes["E101"] == "Hydraulic oil temperature too high"
    assert set(codes) == {"E101", "E102", "E103"}
    engine = {e.code for e in chunks[3].fault_codes}
    assert engine == {"F2040", "SPN 100 FMI 3"}


def test_prose_lines_are_not_fault_codes():
    assert extract_fault_entries("Check oil level first, then inspect.\nStep 1 do this") == []


def test_normalise_code():
    assert normalise_code(" spn  100  fmi 3 ") == "SPN 100 FMI 3"


def test_roundtrip_jsonl(tmp_path, chunks):
    out = tmp_path / "chunks.jsonl"
    save_chunks(chunks, out)
    assert load_chunks(out) == chunks


def test_ingest_dir_and_cli(tmp_path, capsys):
    assert len(ingest_dir(SAMPLE.parent)) == 4
    out = tmp_path / "c.jsonl"
    assert main(["ingest", "--manuals-dir", str(SAMPLE.parent), "--out", str(out)]) == 0
    assert "4 pages" in capsys.readouterr().out
    assert len(load_chunks(out)) == 4
