# equipment-service-manual-troubleshooting-assistant

Enter a fault code or symptom and get step-by-step troubleshooting with page citations from equipment service manuals. Runs on an ordinary laptop CPU with a small local LLM (Ollama) by default; any OpenAI-compatible hosted API is optional.

> Status: scaffold. Ingestion, retrieval, the agent and the UI are tracked in the roadmap below.

<!-- Demo GIF placeholder: docs/demo.gif -->
![demo placeholder](docs/demo.gif)

## Quick start

```bash
pip install -e ".[dev]"
cp .env.example .env
manual-assistant status
pytest
```

With Docker (starts Ollama and the app):

```bash
docker compose up --build
docker compose exec ollama ollama pull qwen2.5:3b-instruct
```

## Configuration

All settings are environment variables prefixed `MANUAL_ASSISTANT_` (see `.env.example`). Point `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` at any OpenAI-compatible endpoint to use a hosted model instead of Ollama.

## Roadmap

- [x] Scaffold
- [ ] PDF ingestion with page-level chunking and metadata
- [ ] Hybrid retrieval (BM25 + embeddings) with page citations
- [ ] Fault-code lookup tool and agent
- [ ] Gradio UI with clickable citations
- [ ] Evaluation set and accuracy report
- [ ] Multilingual answers (EN/DE and more)

## License

MIT
