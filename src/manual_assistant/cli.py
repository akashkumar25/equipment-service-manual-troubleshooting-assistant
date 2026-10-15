"""Command line entry point."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Settings
from .ingest import ingest_dir, load_chunks, save_chunks
from .retrieval import HybridRetriever


def list_manuals(settings: Settings) -> list[str]:
    if not settings.manuals_dir.is_dir():
        return []
    return sorted(p.name for p in settings.manuals_dir.glob("*.pdf"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manual-assistant", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show configuration and discovered manuals")
    ingest = sub.add_parser("ingest", help="split manual PDFs into page chunks (JSONL)")
    ingest.add_argument("--manuals-dir", type=Path, help="directory with PDFs")
    ingest.add_argument("--out", type=Path, default=Path("data/index/chunks.jsonl"))
    search = sub.add_parser("search", help="hybrid search over an ingested index")
    search.add_argument("query")
    search.add_argument("--index", type=Path, default=Path("data/index/chunks.jsonl"))
    search.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args(argv)

    if args.command == "status":
        s = Settings()
        mode = "local" if s.uses_local_llm else "hosted"
        print(f"LLM endpoint: {s.llm_base_url} ({mode}), model: {s.llm_model}")
        manuals = list_manuals(s)
        print(f"Manuals in {s.manuals_dir}: {len(manuals)}")
        for name in manuals:
            print(f"  - {name}")
        return 0
    if args.command == "ingest":
        directory = args.manuals_dir or Settings().manuals_dir
        chunks = ingest_dir(directory)
        save_chunks(chunks, args.out)
        codes = sum(len(c.fault_codes) for c in chunks)
        print(f"{len(chunks)} pages, {codes} fault-code entries -> {args.out}")
        return 0
    if args.command == "search":
        retriever = HybridRetriever(load_chunks(args.index))
        hits = retriever.search(args.query, args.top_k)
        for h in hits:
            first = h.chunk.text.splitlines()[0] if h.chunk.text else ""
            print(f"[{h.citation}] score={h.score:.4f} {first}")
        if not hits:
            print("no matches")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
