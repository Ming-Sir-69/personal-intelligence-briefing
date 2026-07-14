from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from intelligence_briefing.deduplication import classify_candidate, recall_history
from intelligence_briefing.models import Batch, Event, ModelUsage
from intelligence_briefing.storage import StateStore


SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 7, 14, 7, 0, tzinfo=SHANGHAI)


def make_event(
    event_id: str,
    *,
    days_ago: int = 0,
    url: str | None = None,
    fingerprint: str | None = None,
    phase: str = "released",
    change: str = "available",
) -> Event:
    event_at = NOW - timedelta(days=days_ago)
    return Event(
        event_id=event_id,
        status="new_event",
        subject="OpenAI",
        object_name="Codex",
        action="release",
        core_change=change,
        event_at=event_at,
        published_at=event_at,
        discovered_at=event_at,
        canonical_url=url or f"https://example.com/{event_id}",
        fingerprint=fingerprint or event_id,
        source_urls=(url or f"https://example.com/{event_id}",),
        source_type="official",
        importance="high",
        event_phase=phase,
    )


def test_same_url_is_duplicate_even_when_found_again_after_90_days(tmp_path) -> None:
    store = StateStore(tmp_path)
    prior = make_event("old", days_ago=91, url="https://example.com/release", fingerprint="old")
    candidate = make_event("new", url="https://example.com/release", fingerprint="new")
    store.append_event(prior)

    assert classify_candidate(candidate, recall_history(store, candidate, NOW)) == "duplicate"


def test_unrelated_history_older_than_90_days_is_not_recalled(tmp_path) -> None:
    store = StateStore(tmp_path)
    store.append_event(make_event("old", days_ago=91))
    candidate = make_event("candidate", fingerprint="candidate")

    assert recall_history(store, candidate, NOW) == []


def test_same_fingerprint_is_duplicate_when_title_or_media_changes(tmp_path) -> None:
    store = StateStore(tmp_path)
    store.append_event(make_event("official", fingerprint="same-event"))
    candidate = make_event("translated-title", fingerprint="same-event", url="https://news.example/codex")

    assert classify_candidate(candidate, recall_history(store, candidate, NOW)) == "duplicate"


def test_release_after_preview_is_a_substantive_update(tmp_path) -> None:
    store = StateStore(tmp_path)
    store.append_event(make_event("preview", days_ago=1, phase="preview", change="preview announced"))
    candidate = make_event("release", phase="released", change="generally available")

    assert classify_candidate(candidate, recall_history(store, candidate, NOW)) == "substantive_update"


def test_run_records_and_active_index_are_rebuildable_from_event_history(tmp_path) -> None:
    store = StateStore(tmp_path)
    store.append_event(make_event("recent", days_ago=14))
    store.append_event(make_event("old", days_ago=31))
    batch = Batch(
        batch_id="morning-20260714T062000+0800",
        kind="morning",
        status="success",
        started_at=NOW,
        completed_at=NOW,
        errors=(),
        model_usage=(ModelUsage("minimax", "MiniMax-M3", 10, 5),),
    )

    run_path = store.write_run(batch)
    active = store.rebuild_active_events(NOW)

    assert run_path.name == "run-morning-20260714T062000+0800.json"
    assert [event.event_id for event in active] == ["recent"]
