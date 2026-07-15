from datetime import datetime
from zoneinfo import ZoneInfo

from intelligence_briefing.models import Batch, Event, ModelUsage, SourceItem


SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_event_round_trip_preserves_timezone_and_public_metadata() -> None:
    event = Event(
        event_id="evt-openai-codex-20260714",
        status="new_event",
        subject="OpenAI",
        object_name="Codex",
        action="release",
        core_change="parallel agents available",
        event_at=datetime(2026, 7, 14, 6, 0, tzinfo=SHANGHAI),
        published_at=datetime(2026, 7, 14, 6, 10, tzinfo=SHANGHAI),
        discovered_at=datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI),
        canonical_url="https://openai.com/codex",
        fingerprint="fingerprint",
        source_urls=("https://openai.com/codex",),
        source_type="official",
        importance="high",
        event_phase="released",
    )

    restored = Event.from_dict(event.to_dict())

    assert restored == event
    assert "full_text" not in event.to_dict()


def test_model_usage_round_trip_records_only_usage_metadata() -> None:
    usage = ModelUsage(provider="minimax", model="MiniMax-M3", input_tokens=120, output_tokens=45)

    assert ModelUsage.from_dict(usage.to_dict()) == usage


def test_batch_and_source_item_round_trip_preserve_public_operational_fields() -> None:
    source = SourceItem(
        source_id="openai-news",
        title="Codex update",
        url="https://openai.com/news/codex",
        published_at=datetime(2026, 7, 14, 6, 0, tzinfo=SHANGHAI),
        source_type="official",
    )
    batch = Batch(
        batch_id="morning-20260714T062000+0800",
        kind="morning",
        status="partial",
        started_at=datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI),
        completed_at=datetime(2026, 7, 14, 6, 25, tzinfo=SHANGHAI),
        errors=("one source unavailable",),
        model_usage=(ModelUsage("minimax", "MiniMax-M3", 12, 8),),
    )

    assert SourceItem.from_dict(source.to_dict()) == source
    assert Batch.from_dict(batch.to_dict()) == batch
