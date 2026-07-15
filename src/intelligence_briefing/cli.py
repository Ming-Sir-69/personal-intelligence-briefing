"""Local CLI for safe offline candidate-packet validation."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .models import ModelUsage, SourceItem
from .pipeline import run_batch, run_sample_batch
from .runtime import run_live_batch
from .time_window import SHANGHAI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Personal Intelligence Briefing sample batch")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--batch", choices=("morning", "noon"), required=True)
    parser.add_argument("--trigger-type", default="manual", help="execution origin recorded in delivery metadata")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample", action="store_true", help="run only the offline sample; no network or API key")
    mode.add_argument("--live", action="store_true", help="collect configured public feeds and call configured providers")
    mode.add_argument("--simulate", choices=("failed", "partial"), help="offline failure-state validation without secrets")
    arguments = parser.parse_args(argv)
    discovered_at = datetime.now(SHANGHAI)
    if arguments.sample:
        run_sample_batch(arguments.root, arguments.batch, discovered_at, trigger_type=arguments.trigger_type)
    elif arguments.live:
        run_live_batch(arguments.root, arguments.batch, discovered_at, trigger_type=arguments.trigger_type)
    else:
        _run_simulation(arguments.root, arguments.batch, discovered_at, arguments.simulate, arguments.trigger_type)
    return 0


def _run_simulation(root: Path, kind: str, discovered_at: datetime, scenario: str | None, trigger_type: str) -> None:
    source = SourceItem("simulation", "Simulated provider result", "https://example.com/simulated", discovered_at, "official")

    class FailingNormalizer:
        def normalize(self, _source: SourceItem, _discovered_at: datetime) -> tuple[object, ModelUsage]:
            raise RuntimeError("simulated provider failure")

    if scenario == "failed":
        run_batch(root, kind, discovered_at, [source], normalizer=FailingNormalizer(), trigger_type=trigger_type)  # type: ignore[arg-type]
    elif scenario == "partial":
        run_batch(root, kind, discovered_at, [source], collection_errors=("simulation: source timeout",), trigger_type=trigger_type)
    else:
        raise ValueError(f"unsupported simulation scenario: {scenario}")


if __name__ == "__main__":
    raise SystemExit(main())
