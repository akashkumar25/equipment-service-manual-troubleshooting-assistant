"""Command line entry point."""

import argparse
import sys

from . import __version__
from .config import Settings


def list_manuals(settings: Settings) -> list[str]:
    if not settings.manuals_dir.is_dir():
        return []
    return sorted(p.name for p in settings.manuals_dir.glob("*.pdf"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manual-assistant", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show configuration and discovered manuals")
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
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
