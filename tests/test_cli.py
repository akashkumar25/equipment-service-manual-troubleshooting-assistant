from manual_assistant.cli import list_manuals, main
from manual_assistant.config import Settings


def test_defaults_are_local():
    assert Settings().uses_local_llm


def test_hosted_endpoint_detected():
    assert not Settings(llm_base_url="https://api.example.com/v1").uses_local_llm


def test_list_manuals(tmp_path):
    (tmp_path / "b.pdf").write_bytes(b"%PDF")
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "notes.txt").write_text("x")
    assert list_manuals(Settings(manuals_dir=tmp_path)) == ["a.pdf", "b.pdf"]


def test_status_command(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("MANUAL_ASSISTANT_MANUALS_DIR", str(tmp_path))
    assert main(["status"]) == 0
    assert "Manuals in" in capsys.readouterr().out
