from datetime import datetime
import json
from zoneinfo import ZoneInfo

from intelligence_briefing.models import Event, ModelUsage, SourceItem
from intelligence_briefing.pipeline import run_batch, run_sample_batch


def test_sample_batch_generates_a_readable_candidate_packet_without_api_keys(tmp_path) -> None:
    archive = run_sample_batch(tmp_path, "morning", datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai")))

    assert (archive / "manifest.json").exists()
    assert (tmp_path / "delivery/current/morning-preliminary.md").exists()
    assert "API_KEY" not in (archive / "preliminary.md").read_text(encoding="utf-8")


def test_batch_uses_minimax_normalizer_and_records_returned_usage(tmp_path) -> None:
    now = datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai"))

    class FakeNormalizer:
        def normalize(self, source: SourceItem, discovered_at: datetime) -> tuple[Event, ModelUsage]:
            return (
                Event(
                    "evt-model", "new_event", "OpenAI", "Codex", "release", "model-normalized", now, now,
                    discovered_at, source.url, "fp-model", (source.url,), "official", "high", "released",
                ),
                ModelUsage("minimax", "MiniMax-M3", 41, 9),
            )

    source = SourceItem("openai-news", "Codex update", "https://openai.com/codex", now, "official")
    archive = run_batch(tmp_path, "morning", now, [source], normalizer=FakeNormalizer())

    manifest = (archive / "manifest.json").read_text(encoding="utf-8")
    assert '"provider": "minimax"' in manifest


def test_all_normalization_failures_create_failed_archive_without_replacing_current(tmp_path) -> None:
    now = datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai"))
    source = SourceItem("openai-news", "Codex update", "https://openai.com/codex", now, "official")
    run_batch(tmp_path, "morning", now, [source])

    class FailingNormalizer:
        def normalize(self, _source: SourceItem, _discovered_at: datetime) -> tuple[Event, ModelUsage]:
            raise RuntimeError("provider timeout")

    failed_archive = run_batch(tmp_path, "noon", now, [source], normalizer=FailingNormalizer())

    failed_manifest = json.loads((failed_archive / "manifest.json").read_text(encoding="utf-8"))
    current_manifest = json.loads((tmp_path / "delivery/current/manifest.json").read_text(encoding="utf-8"))
    assert failed_manifest["status"] == "failed"
    assert current_manifest["kind"] == "morning"


def test_partial_batch_is_archived_without_replacing_current(tmp_path) -> None:
    now = datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai"))
    first = SourceItem("openai-news", "Codex update", "https://openai.com/codex", now, "official")
    second = SourceItem("anthropic-news", "Claude update", "https://anthropic.com/claude", now, "official")
    run_batch(tmp_path, "morning", now, [first])

    class PartiallyFailingNormalizer:
        def normalize(self, source: SourceItem, discovered_at: datetime) -> tuple[Event, ModelUsage]:
            if source.source_id == "openai-news":
                raise RuntimeError("provider timeout")
            return (
                Event(
                    "evt-ok", "new_event", "Anthropic", "Claude Code", "release", "update", now, now,
                    discovered_at, source.url, "fp-ok", (source.url,), "official", "high", "released",
                ),
                ModelUsage("minimax", "MiniMax-M3", 10, 5),
            )

    partial_archive = run_batch(tmp_path, "noon", now, [first, second], normalizer=PartiallyFailingNormalizer())

    partial_manifest = json.loads((partial_archive / "manifest.json").read_text(encoding="utf-8"))
    current_manifest = json.loads((tmp_path / "delivery/current/manifest.json").read_text(encoding="utf-8"))
    assert partial_manifest["status"] == "partial"
    assert current_manifest["kind"] == "morning"


def test_recent_events_are_prior_successful_gpt_handoffs_not_a_copy_of_current_batch(tmp_path) -> None:
    morning = datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai"))
    noon = datetime(2026, 7, 14, 12, 20, tzinfo=ZoneInfo("Asia/Shanghai"))
    first = SourceItem("openai-news", "First update", "https://example.com/first", morning, "official")
    second = SourceItem("anthropic-news", "Second update", "https://example.com/second", noon, "official")

    run_batch(tmp_path, "morning", morning, [first])
    run_batch(tmp_path, "noon", noon, [second])

    recent = json.loads((tmp_path / "delivery/current/recent-events.json").read_text(encoding="utf-8"))
    current = json.loads((tmp_path / "delivery/current/noon-candidates.json").read_text(encoding="utf-8"))
    assert [item["batch_id"] for item in recent] == ["morning-20260714T062000+0800"]
    assert current["sections"]["batch_state_and_range"]["batch_id"] == "noon-20260714T122000+0800"
