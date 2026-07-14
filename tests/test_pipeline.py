from datetime import datetime
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
