"""Live public-feed runtime wiring for GitHub Actions."""

from __future__ import annotations

from datetime import datetime
from functools import partial
import os
from pathlib import Path
from typing import Callable, Mapping

from .collectors import collect_feeds_safely, fetch_url, select_recent_feed_items
from .config import load_candidate_selection, load_enabled_sources, load_model_route
from .llm import KimiArbitrator, MiniMaxNormalizer, OpenAICompatibleClient, http_post_json
from .models import ModelUsage, SourceItem
from .pipeline import run_batch
from .storage import StateStore
from .time_window import report_window


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
    environment = os.environ if environment is None else environment
    source_config = root / "config" / "sources-official-v1.yml"
    sources = load_enabled_sources(source_config)
    selection = load_candidate_selection(source_config)
    collected, collection_errors = collect_feeds_safely(sources, fetch=fetch)
    window = report_window(kind, discovered_at, previous_success_at=StateStore(root).last_successful_completed_at())
    collected = select_recent_feed_items(collected, window, **selection)
    minimax_route = load_model_route(root / "config" / "model-routing-v1.yml", "minimax")
    minimax_secret_name = str(minimax_route["secret_name"])
    minimax_key = environment.get(minimax_secret_name)
    if minimax_key:
        minimax_client = OpenAICompatibleClient(
            "minimax",
            str(minimax_route["base_url"]),
            str(minimax_route["preferred_models"][0]),
            minimax_key,
            partial(http_post_json, timeout_seconds=int(minimax_route.get("timeout_seconds", 30))),
            request_options=dict(minimax_route.get("request_options", {})),
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
            partial(http_post_json, timeout_seconds=int(kimi_route.get("timeout_seconds", 30))),
            request_options=dict(kimi_route.get("request_options", {})),
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
