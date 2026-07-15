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
from .time_window import report_window
from .url_normalization import normalize_url


def event_from_source(source: SourceItem, discovered_at: datetime) -> Event:
    event_at = None
    fingerprint = event_fingerprint(source.source_id, source.title, "published", None, source.title)
    canonical_url = normalize_url(source.url)
    return Event(
        event_id=f"evt-{sha256((fingerprint + canonical_url).encode()).hexdigest()[:16]}",
        status="uncertain",
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
    collection_errors: tuple[str, ...] = (),
    trigger_type: str = "manual",
) -> Path:
    store = StateStore(root)
    window = report_window(kind, discovered_at, previous_success_at=store.last_successful_completed_at())
    classified: list[Event] = []
    usage = []
    errors: list[str] = list(collection_errors)
    normalization_failures = 0
    for source in sources:
        if normalizer:
            try:
                event, model_usage = normalizer.normalize(source, discovered_at)
                usage.append(model_usage)
            except (RuntimeError, ValueError) as error:
                event = replace(event_from_source(source, discovered_at), status="uncertain")
                normalization_failures += 1
                errors.append(f"minimax normalization failed for {source.source_id}: {error}")
        else:
            event = event_from_source(source, discovered_at)
        status = classify_candidate(event, recall_history(store, event, discovered_at), discovered_at)
        if event.event_at is None and status != "duplicate":
            status = "uncertain"
        classified.append(replace(event, status=status))
    if kimi_arbitrator:
        for candidate in select_kimi_candidates(classified):
            status, model_usage = kimi_arbitrator.arbitrate_safely(candidate, recall_history(store, candidate, discovered_at))
            if model_usage:
                usage.append(model_usage)
            else:
                errors.append(f"kimi arbitration failed for {candidate.event_id}")
            classified = [replace(event, status=status) if event.event_id == candidate.event_id else event for event in classified]
    classified = [
        replace(event, status="uncertain") if event.status == "needs_semantic_review" else event
        for event in classified
    ]
    batch_id = f"{kind}-{discovered_at:%Y%m%dT%H%M%S%z}"
    if not sources and collection_errors:
        batch_status = "failed"
    elif normalizer and sources and normalization_failures == len(sources):
        batch_status = "failed"
    elif errors:
        batch_status = "partial"
    else:
        batch_status = "success"
    batch = Batch(
        batch_id, kind, batch_status, discovered_at, discovered_at, tuple(errors), tuple(usage), trigger_type=trigger_type,
    )
    for event in classified:
        store.append_event(event)
    store.write_run(batch)
    store.rebuild_active_events(discovered_at)
    writer = DeliveryWriter(root)
    recent_events = store.recent_gpt_handoffs(discovered_at)
    archive = writer.write(
        batch,
        classified,
        source_commit_sha=os.environ.get("GITHUB_SHA", "local-dry-run"),
        workflow_run_id=os.environ.get("GITHUB_RUN_ID"),
        recent_events=recent_events,
        window=window,
    )
    if batch.status == "success":
        store.append_gpt_handoffs(batch, classified)
        store.write_successful_watermark(batch)
    return archive


def run_sample_batch(root: Path, kind: str, discovered_at: datetime, *, trigger_type: str = "sample") -> Path:
    source = SourceItem(
        source_id="sample-official-source",
        title="Sample AI product update",
        url="https://example.com/briefing-sample?utm_source=local",
        published_at=discovered_at,
        source_type="official",
    )
    return run_batch(root, kind, discovered_at, [source], trigger_type=trigger_type)
