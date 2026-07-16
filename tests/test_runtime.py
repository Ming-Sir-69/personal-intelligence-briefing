from datetime import datetime
import json
from zoneinfo import ZoneInfo

from intelligence_briefing.models import Event, ModelUsage, SourceItem
from intelligence_briefing.pipeline import run_batch
from intelligence_briefing.runtime import run_live_batch


RSS = b"""<?xml version='1.0'?>
<rss><channel><item>
  <title>Codex release</title>
  <link>https://openai.com/news/codex</link>
  <pubDate>Mon, 14 Jul 2026 06:00:00 +0800</pubDate>
</item></channel></rss>"""


def _write_runtime_config(root) -> None:
    config = root / "config"
    config.mkdir()
    (config / "sources-official-v1.yml").write_text(
        "version: 1\nsources:\n  - id: openai-news\n    url: https://example.com/rss\n    source_type: official\n    enabled: true\n",
        encoding="utf-8",
    )
    (config / "model-routing-v1.yml").write_text(
        "version: 1\nminimax:\n  secret_name: MINIMAX_FOR_CODING_API_KEY\n  base_url: https://api.example/v1\n  preferred_models: [MiniMax-M3]\n  request_options:\n    max_tokens: 512\n    thinking: {type: disabled}\nkimi:\n  secret_name: KIMI_API_KEY\n  base_url: https://api.example/v1\n  preferred_models: [kimi-k2.6]\n",
        encoding="utf-8",
    )


def test_live_runtime_uses_configured_feed_and_minimax_secret(tmp_path, monkeypatch) -> None:
    _write_runtime_config(tmp_path)
    observed: dict[str, object] = {}

    def request_json(_url, _headers, payload, **kwargs):
        observed.update(payload)
        observed["timeout_seconds"] = kwargs["timeout_seconds"]
        return 200, {
            "id": "minimax-test",
            "choices": [{"message": {"content": json.dumps({
                "status": "new_event", "subject": "OpenAI", "object_name": "Codex",
                "action": "release", "core_change": "update", "event_at": "2026-07-14T06:00:00+08:00",
                "importance": "high", "event_phase": "released", "fact_type": "software_release",
            })}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }

    monkeypatch.setattr("intelligence_briefing.runtime.http_post_json", request_json)
    archive = run_live_batch(
        tmp_path,
        "morning",
        datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
        fetch=lambda _url: RSS,
        environment={"MINIMAX_FOR_CODING_API_KEY": "test-key"},
        trigger_type="schedule",
    )

    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "success"
    assert manifest["model_usage"] == [{"provider": "minimax", "model": "MiniMax-M3", "input_tokens": 11, "output_tokens": 7, "request_id": "minimax-test"}]
    assert observed["thinking"] == {"type": "disabled"}
    assert observed["max_tokens"] == 512
    assert observed["timeout_seconds"] == 30
    assert manifest["trigger_type"] == "schedule"
    assert manifest["coverage_mode"] == "scheduled_increment"
    candidates = json.loads((archive / "candidates.json").read_text(encoding="utf-8"))
    review = candidates["gpt_review_plan"]["candidate_reviews"][0]
    assert review["review_level"] == "required"
    assert candidates["normalization_audit"]["flag_counts"] == {"feed_time_metadata": 1}


def test_live_runtime_missing_minimax_secret_does_not_fall_back_to_process_environment(tmp_path, monkeypatch) -> None:
    _write_runtime_config(tmp_path)
    monkeypatch.setenv("MINIMAX_FOR_CODING_API_KEY", "ambient-test-key")

    def unexpected_provider_call(_url, _headers, _payload):
        return 200, {
            "choices": [{"message": {"content": json.dumps({
                "status": "new_event", "subject": "OpenAI", "object_name": "Codex",
                "action": "release", "core_change": "update", "event_at": "2026-07-14T06:00:00+08:00",
                "importance": "high", "event_phase": "released", "fact_type": "software_release",
            })}}],
            "usage": {},
        }

    monkeypatch.setattr("intelligence_briefing.runtime.http_post_json", unexpected_provider_call)

    archive = run_live_batch(
        tmp_path,
        "morning",
        datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
        fetch=lambda _url: RSS,
        environment={},
    )

    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert "MINIMAX_FOR_CODING_API_KEY" in manifest["errors"][0]
    assert not (tmp_path / "delivery/current").exists()


def test_live_runtime_routes_only_a_high_priority_ambiguous_event_to_kimi(tmp_path, monkeypatch) -> None:
    _write_runtime_config(tmp_path)
    previous = datetime(2026, 7, 14, 6, 10, tzinfo=ZoneInfo("Asia/Shanghai"))

    class PreviousNormalizer:
        def normalize(self, source: SourceItem, discovered_at: datetime) -> tuple[Event, ModelUsage]:
            return (
                Event(
                    "evt-previous", "new_event", "OpenAI", "Codex", "release", "previous capability",
                    previous, previous, discovered_at, "https://openai.com/previous", "previous-fingerprint",
                    ("https://openai.com/previous",), "official", "high", "released", "software_release",
                ),
                ModelUsage("minimax", "MiniMax-M3", 1, 1),
            )

    run_batch(
        tmp_path,
        "morning",
        previous,
        [SourceItem("openai-news", "Previous", "https://openai.com/previous", previous, "official")],
        normalizer=PreviousNormalizer(),
    )
    observed_providers: list[str] = []

    def request_json(_url, headers, _payload, **_kwargs):
        authorization = headers["Authorization"]
        observed_providers.append(authorization)
        if authorization == "Bearer kimi-key":
            content = json.dumps({"status": "substantive_update", "reason": "material change"})
            provider = "kimi-test"
        else:
            content = json.dumps({
                "status": "new_event", "subject": "OpenAI", "object_name": "Codex",
                "action": "release", "core_change": "new capability",
                "event_at": "2026-07-14T06:00:00+08:00", "importance": "high",
                "event_phase": "released", "fact_type": "software_release",
            })
            provider = "minimax-test"
        return 200, {
            "id": provider,
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }

    monkeypatch.setattr("intelligence_briefing.runtime.http_post_json", request_json)
    archive = run_live_batch(
        tmp_path,
        "noon",
        datetime(2026, 7, 14, 12, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
        fetch=lambda _url: RSS,
        environment={
            "MINIMAX_FOR_CODING_API_KEY": "minimax-key",
            "KIMI_API_KEY": "kimi-key",
        },
        trigger_type="schedule",
    )

    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    candidates = json.loads((archive / "candidates.json").read_text(encoding="utf-8"))
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in (tmp_path / "data", tmp_path / "delivery")
        for path in directory.rglob("*")
        if path.is_file()
    )
    assert observed_providers == ["Bearer minimax-key", "Bearer kimi-key"]
    assert [usage["provider"] for usage in manifest["model_usage"]] == ["minimax", "kimi"]
    assert candidates["sections"]["must_know"][0]["status"] == "substantive_update"
    assert "minimax-key" not in persisted
    assert "kimi-key" not in persisted
