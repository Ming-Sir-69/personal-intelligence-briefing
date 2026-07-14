"""Offline-safe candidate batch orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import os
from pathlib import Path

from .deduplication import classify_candidate, recall_history
from .fingerprints import event_fingerprint
from .llm import KimiArbitrator, MiniMaxNormalizer, select_kimi_candidates
from .models import Batch, Event, SourceItem
from .reporting import DeliveryWriter
from .storage import StateStore
from .url_normalization import normalize_url


def event_from_source(source: SourceItem, discovered_at: datetime) -> Event:
    event_at = source.published_at or discovered_at
    fingerprint = event_fingerprint(source.source_id, source.title, "published", event_at.date(), source.title)
    canonical_url = normalize_url(source.url)
    return Event(
        event_id=f"evt-{sha256((fingerprint + canonical_url).encode()).hexdigest()[:16]}",
        status="new_event",
        subject=source.source_id,
        object_name=source.title,
        action="published",
        core_change=source.title,
        event_at=event_at,
        published_at=source.published_at,
        discovered_at=discovered_at,
        canonical_url=canonical_url,
        fingerprint=fingerprint,
        source_urls=(canonical_url,),
        source_type=source.source_type,
        importance="medium",
        event_phase="",
    )


def run_batch(
    root: Path,
    kind: str,
    discovered_at: datetime,
    sources: list[SourceItem],
    *,
    normalizer: MiniMaxNormalizer | None = None,
    kimi_arbitrator: KimiArbitrator | None = None,
) -> Path:
    store = StateStore(root)
    classified: list[Event] = []
    usage = []
    errors: list[str] = []
    for source in sources:
        if normalizer:
            try:
                event, model_usage = normalizer.normalize(source, discovered_at)
                usage.append(model_usage)
            except (RuntimeError, ValueError) as error:
                event = replace(event_from_source(source, discovered_at), status="uncertain")
                errors.append(f"minimax normalization failed for {source.source_id}: {error}")
        else:
            event = event_from_source(source, discovered_at)
        status = classify_candidate(event, recall_history(store, event, discovered_at))
        if status == "needs_semantic_review":
            status = "uncertain"
        classified.append(replace(event, status=status))
    if kimi_arbitrator:
        for candidate in select_kimi_candidates(classified):
            status, model_usage = kimi_arbitrator.arbitrate_safely(candidate, recall_history(store, candidate, discovered_at))
            if model_usage:
                usage.append(model_usage)
            classified = [replace(event, status=status) if event.event_id == candidate.event_id else event for event in classified]
    batch_id = f"{kind}-{discovered_at:%Y%m%dT%H%M%S%z}"
    batch = Batch(batch_id, kind, "success", discovered_at, discovered_at, tuple(errors), tuple(usage))
    for event in classified:
        store.append_event(event)
    store.write_run(batch)
    store.rebuild_active_events(discovered_at)
    return DeliveryWriter(root).write(batch, classified, git_commit_sha=os.environ.get("GITHUB_SHA", "local-dry-run"))


def run_sample_batch(root: Path, kind: str, discovered_at: datetime) -> Path:
    source = SourceItem(
        source_id="sample-official-source",
        title="Sample AI product update",
        url="https://example.com/briefing-sample?utm_source=local",
        published_at=discovered_at,
        source_type="official",
    )
    return run_batch(root, kind, discovered_at, [source])
