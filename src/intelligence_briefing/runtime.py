"""Live public-feed runtime wiring for GitHub Actions."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Callable, Mapping

from .collectors import collect_feeds_safely, fetch_url
from .config import load_enabled_sources, load_model_route
from .llm import KimiArbitrator, MiniMaxNormalizer, OpenAICompatibleClient, http_post_json
from .models import ModelUsage, SourceItem
from .pipeline import run_batch


class _UnavailableNormalizer:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def normalize(self, _source: SourceItem, _discovered_at: datetime) -> tuple[object, ModelUsage]:
        raise RuntimeError(self.reason)


def run_live_batch(
    root: Path,
    kind: str,
    discovered_at: datetime,
    *,
    fetch: Callable[[str], bytes] = fetch_url,
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Collect configured public metadata and send it through the live routes."""
    environment = environment or os.environ
    sources = load_enabled_sources(root / "config" / "sources-official-v1.yml")
    collected, collection_errors = collect_feeds_safely(sources, fetch=fetch)
    minimax_route = load_model_route(root / "config" / "model-routing-v1.yml", "minimax")
    minimax_secret_name = str(minimax_route["secret_name"])
    minimax_key = environment.get(minimax_secret_name)
    if minimax_key:
        minimax_client = OpenAICompatibleClient(
            "minimax",
            str(minimax_route["base_url"]),
            str(minimax_route["preferred_models"][0]),
            minimax_key,
            http_post_json,
        )
        normalizer = MiniMaxNormalizer(minimax_client)
    else:
        normalizer = _UnavailableNormalizer(f"required GitHub Actions secret {minimax_secret_name} is unavailable")
        collection_errors += (f"configuration: required secret {minimax_secret_name} is unavailable",)

    kimi_arbitrator = None
    kimi_route = load_model_route(root / "config" / "model-routing-v1.yml", "kimi")
    kimi_secret_name = str(kimi_route["secret_name"])
    kimi_key = environment.get(kimi_secret_name)
    if kimi_key:
        kimi_client = OpenAICompatibleClient(
            "kimi",
            str(kimi_route["base_url"]),
            str(kimi_route["preferred_models"][0]),
            kimi_key,
            http_post_json,
        )
        kimi_arbitrator = KimiArbitrator(kimi_client)

    return run_batch(
        root,
        kind,
        discovered_at,
        collected,
        normalizer=normalizer,  # type: ignore[arg-type]
        kimi_arbitrator=kimi_arbitrator,
        collection_errors=collection_errors,
    )
