from pathlib import Path

from manual_assistant.agent import TroubleshootingAgent
from manual_assistant.evaluate import EvalQuestion, evaluate, load_questions, to_markdown
from manual_assistant.ingest import ingest_dir
from manual_assistant.retrieval import HybridRetriever

EVAL = Path(__file__).resolve().parents[1] / "data" / "eval"


def test_question_set_is_large_and_well_formed():
    questions = load_questions(EVAL / "questions.jsonl")
    assert len(questions) >= 50
    manuals = {p.name for p in (EVAL / "manuals").glob("*.pdf")}
    assert {q.manual for q in questions} <= manuals
    assert all(q.pages and q.keywords for q in questions)


def test_code_questions_cite_the_right_page():
    chunks = ingest_dir(EVAL / "manuals")
    agent = TroubleshootingAgent(HybridRetriever(chunks))
    questions = [q for q in load_questions(EVAL / "questions.jsonl") if q.kind == "code"]
    report = evaluate(agent, questions, chunks)
    assert report["overall"]["agent_citation"] >= 0.9
    assert report["overall"]["answer_support"] >= 0.9


def test_wrong_label_scores_zero_and_markdown_renders():
    chunks = ingest_dir(EVAL / "manuals")
    agent = TroubleshootingAgent(HybridRetriever(chunks))
    bad = EvalQuestion(
        question="What does H101 mean?", kind="code", manual="nope.pdf", pages=[1], keywords=["zzz"]
    )
    report = evaluate(agent, [bad], chunks)
    assert report["overall"]["top3"] == 0 and report["overall"]["answer_support"] == 0
    assert "| overall | 1 |" in to_markdown(report)
