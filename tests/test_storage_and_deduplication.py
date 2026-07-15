from dataclasses import replace
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
    batch = Batch("morning-20260714T062000+0800", "morning", "success", NOW, NOW, (), ())
    store.append_gpt_handoffs(batch, [prior])

    assert classify_candidate(candidate, recall_history(store, candidate, NOW)) == "duplicate"


def test_unrelated_history_older_than_90_days_is_not_recalled(tmp_path) -> None:
    store = StateStore(tmp_path)
    store.append_event(make_event("old", days_ago=91))
    candidate = make_event("candidate", fingerprint="candidate")

    assert recall_history(store, candidate, NOW) == []


def test_same_fingerprint_is_duplicate_when_title_or_media_changes(tmp_path) -> None:
    store = StateStore(tmp_path)
    prior = make_event("official", fingerprint="same-event")
    batch = Batch("morning-20260714T062000+0800", "morning", "success", NOW, NOW, (), ())
    store.append_gpt_handoffs(batch, [prior])
    candidate = make_event("translated-title", fingerprint="same-event", url="https://news.example/codex")

    assert classify_candidate(candidate, recall_history(store, candidate, NOW)) == "duplicate"


def test_release_after_preview_is_a_substantive_update(tmp_path) -> None:
    store = StateStore(tmp_path)
    preview = make_event("preview", days_ago=1, phase="preview", change="preview announced")
    batch = Batch("morning-20260714T062000+0800", "morning", "success", NOW, NOW, (), ())
    store.append_gpt_handoffs(batch, [preview])
    candidate = make_event("release", phase="released", change="generally available")

    assert classify_candidate(candidate, recall_history(store, candidate, NOW)) == "substantive_update"


def test_history_recall_uses_distinct_rules_for_all_four_media_echo_bands(tmp_path) -> None:
    store = StateStore(tmp_path)
    candidate = make_event("candidate", fingerprint="candidate")

    for days_ago in (14, 15, 30):
        prior = make_event(f"chain-{days_ago}", days_ago=days_ago)
        batch = Batch("morning-20260714T062000+0800", "morning", "success", NOW, NOW, (), ())
        store.append_gpt_handoffs(batch, [prior])
        assert prior.event_id in {event.event_id for event in recall_history(store, candidate, NOW)}

    for days_ago in (31, 60, 61, 90):
        prior = make_event(f"not-recalled-{days_ago}", days_ago=days_ago)
        batch = Batch("morning-20260714T062000+0800", "morning", "success", NOW, NOW, (), ())
        store.append_gpt_handoffs(batch, [prior])
        assert prior.event_id not in {event.event_id for event in recall_history(store, candidate, NOW)}


def test_unknown_event_time_never_enters_chain_based_history_recall(tmp_path) -> None:
    store = StateStore(tmp_path)
    unknown_time = replace(make_event("unknown-time"), event_at=None, published_at=NOW, discovered_at=NOW)
    store.append_event(unknown_time)

    candidate = make_event("candidate", fingerprint="candidate")

    assert recall_history(store, candidate, NOW) == []


def test_hot_chain_can_escalate_to_semantic_review_but_warm_chain_cannot(tmp_path) -> None:
    store = StateStore(tmp_path)
    candidate = make_event("candidate", fingerprint="candidate", change="different capability")
    hot = make_event("hot", days_ago=14, change="earlier capability")
    warm = make_event("warm", days_ago=15, change="earlier capability")

    batch = Batch("morning-20260714T062000+0800", "morning", "success", NOW, NOW, (), ())
    store.append_gpt_handoffs(batch, [hot])
    assert classify_candidate(candidate, recall_history(store, candidate, NOW), NOW) == "needs_semantic_review"

    isolated_store = StateStore(tmp_path / "warm-only")
    isolated_store.append_gpt_handoffs(batch, [warm])
    assert classify_candidate(candidate, recall_history(isolated_store, candidate, NOW), NOW) == "uncertain"


def test_observed_event_from_partial_batch_does_not_suppress_first_successful_delivery(tmp_path) -> None:
    store = StateStore(tmp_path)
    observed = make_event("observed-only", fingerprint="same-event")
    candidate = make_event("first-success", fingerprint="same-event")

    store.append_event(observed)

    assert classify_candidate(candidate, recall_history(store, candidate, NOW), NOW) == "new_event"


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
