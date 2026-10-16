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

## Ingest a manual

Drop service-manual PDFs into `data/manuals/` (a fictional sample lives in `data/samples/`) and run:

```bash
manual-assistant ingest --manuals-dir data/samples
```

This writes `data/index/chunks.jsonl`: one chunk per PDF page with the manual name, page number, detected model, system/section and any fault-code table rows (`E101  Hydraulic oil temperature too high`). The sample manual is regenerated with `python scripts/make_sample_manual.py` (needs `reportlab`).

## Search

```bash
manual-assistant search "E101" --index data/index/chunks.jsonl
manual-assistant search "engine overheating coolant"
```

Retrieval fuses BM25 keyword ranking (fault codes such as `E101` stay whole tokens) with dense embeddings via reciprocal rank fusion. Each hit is a page, printed as `[manual.pdf, p. 3]`. The default embedder is an offline character n-gram hashing embedder (no model download, works in any language). For semantic multilingual embeddings install `pip install -e ".[embeddings]"` and pass `SentenceTransformerEmbedder()` to `HybridRetriever`.

## Ask (fault-code tool + agent)

```bash
manual-assistant lookup E101                      # exact table lookup, with page citation
manual-assistant ask "What does E101 mean?"       # LLM answer from tool result + retrieved pages
manual-assistant ask "E101" --no-llm              # evidence only, fully offline
```

The agent extracts fault codes from the question (`E101`, `F-2040`, `SPN 100 FMI 3`), looks them up exactly in the tables captured at ingestion, retrieves the best pages with hybrid search and asks the LLM to answer only from that evidence, citing `[manual, p. N]`. Citations the model invents are dropped. If the LLM endpoint is unreachable the agent falls back to an extractive, still-cited answer.

## Configuration

All settings are environment variables prefixed `MANUAL_ASSISTANT_` (see `.env.example`). Point `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` at any OpenAI-compatible endpoint to use a hosted model instead of Ollama.

## Roadmap

- [x] Scaffold
- [x] PDF ingestion with page-level chunking and metadata
- [x] Hybrid retrieval (BM25 + embeddings) with page citations
- [x] Fault-code lookup tool and agent
- [ ] Gradio UI with clickable citations
- [ ] Evaluation set and accuracy report
- [ ] Multilingual answers (EN/DE and more)

## License

MIT
