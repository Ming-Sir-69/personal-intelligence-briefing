from datetime import datetime
import json
from zoneinfo import ZoneInfo

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
                "importance": "high", "event_phase": "released",
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


def test_live_runtime_missing_minimax_secret_does_not_fall_back_to_process_environment(tmp_path, monkeypatch) -> None:
    _write_runtime_config(tmp_path)
    monkeypatch.setenv("MINIMAX_FOR_CODING_API_KEY", "ambient-test-key")

    def unexpected_provider_call(_url, _headers, _payload):
        return 200, {
            "choices": [{"message": {"content": json.dumps({
                "status": "new_event", "subject": "OpenAI", "object_name": "Codex",
                "action": "release", "core_change": "update", "event_at": "2026-07-14T06:00:00+08:00",
                "importance": "high", "event_phase": "released",
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
