"""Local CLI for safe offline candidate-packet validation."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .pipeline import run_sample_batch
from .time_window import SHANGHAI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Personal Intelligence Briefing sample batch")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--batch", choices=("morning", "noon"), required=True)
    parser.add_argument("--sample", action="store_true", help="run only the offline sample; no network or API key")
    arguments = parser.parse_args(argv)
    if not arguments.sample:
        parser.error("MVP currently supports only --sample; live collection is added in G3")
    run_sample_batch(arguments.root, arguments.batch, datetime.now(SHANGHAI))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
