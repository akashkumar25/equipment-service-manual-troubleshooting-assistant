from pathlib import Path

import pytest

from manual_assistant.agent import TroubleshootingAgent
from manual_assistant.i18n import detect_language, expand_query
from manual_assistant.ingest import ingest_dir
from manual_assistant.retrieval import HybridRetriever

EVAL = Path(__file__).resolve().parent.parent / "data" / "eval" / "manuals"


@pytest.fixture(scope="module")
def agent():
    return TroubleshootingAgent(HybridRetriever(ingest_dir(EVAL)))


@pytest.mark.parametrize(
    "text,lang",
    [
        ("What does H101 mean?", "en"),
        ("Was bedeutet der Fehlercode H101?", "de"),
        ("Das Hydrauliköl wird nach einer Stunde zu heiß. Was soll ich prüfen?", "de"),
        ("Que signifie le code H101 et comment puis-je le corriger ?", "fr"),
        ("¿Qué significa el fallo H101 y cómo puedo arreglarlo?", "es"),
        ("Cosa significa il codice H101 e come posso risolverlo?", "it"),
        ("H101", "en"),
    ],
)
def test_detect_language(text, lang):
    assert detect_language(text) == lang


def test_expand_query_adds_english_terms():
    q = expand_query("Das Hydrauliköl ist zu heiß", "de")
    assert "hydraulic oil" in q and "hot" in q
    assert expand_query("hydraulic oil hot", "en") == "hydraulic oil hot"
    assert "hydraulic oil" in expand_query("huile hydraulique trop chaude", "fr")


def test_german_symptom_retrieves_english_page(agent):
    ans = agent.ask("Das Hydrauliköl wird nach einer Stunde Ladearbeit zu heiß. Was prüfen?")
    assert ans.language == "de"
    assert any("bx150" in c for c in ans.citations)
    assert "Siehe" in ans.text


def test_explicit_language_overrides_detection(agent):
    ans = agent.ask("What does H101 mean?", language="fr")
    assert ans.language == "fr"
    assert "Voir" in ans.text
    assert ans.fault_matches  # exact code lookup is language independent


def test_llm_prompt_names_target_language(agent):
    seen = {}

    class Spy:
        def complete(self, system, user):
            seen["user"] = user
            return "1. Prüfen Sie den Ölstand. [bx150_wheel_loader.pdf, p. 3]"

    a = TroubleshootingAgent(agent.retriever, Spy())
    ans = a.ask("Was bedeutet H101?")
    assert "Answer in German" in seen["user"]
    assert ans.used_llm and ans.language == "de"
