import urllib.error
from pathlib import Path

import pytest

from manual_assistant.agent import TroubleshootingAgent
from manual_assistant.cli import main
from manual_assistant.ingest import FaultEntry, PageChunk, ingest_dir
from manual_assistant.retrieval import HybridRetriever
from manual_assistant.tools import FaultCodeLookup, find_codes

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


@pytest.fixture(scope="module")
def chunks():
    return ingest_dir(SAMPLES)


def test_find_codes_variants():
    assert find_codes("Showing e101 and spn 100 fmi 3, also F-2040") == [
        "E101",
        "SPN 100 FMI 3",
        "F-2040",
    ]
    assert find_codes("an engine overheating problem") == []


def test_lookup_ignores_dash_and_case():
    chunk = PageChunk(
        manual="m.pdf",
        page=4,
        text="x",
        model="TX-200",
        fault_codes=[FaultEntry(code="F-2040", description="Pump pressure low")],
    )
    lk = FaultCodeLookup([chunk])
    assert lk.lookup("f2040")[0].citation == "m.pdf, p. 4"
    assert lk.lookup("F-2040", model="tx") != []
    assert lk.lookup("F-2040", model="zz") == []
    assert lk.lookup("E999") == []


def test_lookup_on_sample_manual(chunks):
    lk = FaultCodeLookup(chunks)
    codes = {c.code for ch in chunks for c in ch.fault_codes}
    assert codes
    code = min(codes)
    assert lk.lookup(code)


class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.prompts = reply, error, []

    def complete(self, system, user):
        self.prompts.append(user)
        if self.error:
            raise self.error
        return self.reply


def test_agent_offline_fallback_cites_table_page(chunks):
    code = min({c.code for ch in chunks for c in ch.fault_codes})
    agent = TroubleshootingAgent(HybridRetriever(chunks), llm=None)
    ans = agent.ask(f"What does {code} mean?")
    assert not ans.used_llm
    assert ans.fault_matches
    assert ans.fault_matches[0].citation in ans.citations
    assert code in ans.text


def test_agent_llm_prompt_contains_tool_result_and_filters_citations(chunks):
    code = min({c.code for ch in chunks for c in ch.fault_codes})
    retriever = HybridRetriever(chunks)
    match = FaultCodeLookup(chunks).lookup(code)[0]
    llm = FakeLLM(reply=f"1. Check it [{match.citation}] and [invented.pdf, p. 99]")
    ans = TroubleshootingAgent(retriever, llm).ask(f"{code} fault")
    assert ans.used_llm
    assert code in llm.prompts[0] and match.description in llm.prompts[0]
    assert ans.citations == [match.citation]  # invented source dropped


def test_agent_falls_back_when_llm_unreachable(chunks):
    llm = FakeLLM(error=urllib.error.URLError("refused"))
    ans = TroubleshootingAgent(HybridRetriever(chunks), llm).ask("hydraulic oil temperature")
    assert not ans.used_llm and ans.citations


def test_agent_no_evidence():
    ans = TroubleshootingAgent(HybridRetriever([]), None).ask("anything")
    assert ans.citations == [] and "No relevant" in ans.text


def test_cli_lookup_and_ask(tmp_path, chunks, capsys):
    index = tmp_path / "chunks.jsonl"
    from manual_assistant.ingest import save_chunks

    save_chunks(chunks, index)
    code = min({c.code for ch in chunks for c in ch.fault_codes})
    assert main(["lookup", code, "--index", str(index)]) == 0
    assert main(["lookup", "ZZ999", "--index", str(index)]) == 1
    capsys.readouterr()
    assert main(["ask", f"what is {code}", "--index", str(index), "--no-llm"]) == 0
    assert "Sources:" in capsys.readouterr().out
