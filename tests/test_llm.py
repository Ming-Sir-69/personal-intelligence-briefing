from datetime import datetime
import json
from zoneinfo import ZoneInfo

import pytest

from intelligence_briefing.llm import (
    KimiArbitrator,
    MiniMaxNormalizer,
    ModelReply,
    OpenAICompatibleClient,
    http_post_json,
    select_kimi_candidates,
    should_use_kimi,
)
from intelligence_briefing.models import Event, ModelUsage, SourceItem


SHANGHAI = ZoneInfo("Asia/Shanghai")


class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[dict[str, object]] = []

    def complete(self, payload: dict[str, object]) -> ModelReply:
        self.requests.append(payload)
        return ModelReply(
            content=self.content,
            usage=ModelUsage("fake", "fake-model", 30, 12),
            request_id="request-1",
        )


def test_minimax_normalizer_validates_structured_public_event_and_usage() -> None:
    reply = json.dumps(
        {
            "status": "new_event",
            "subject": "OpenAI",
            "object_name": "Codex",
            "action": "release",
            "core_change": "new coding capability",
            "event_at": "2026-07-14T06:00:00+08:00",
            "importance": "high",
            "event_phase": "released",
            "fact_type": "software_release",
        }
    )
    client = FakeClient(reply)
    source = SourceItem("openai-news", "Codex update", "https://openai.com/codex", None, "official")

    event, usage = MiniMaxNormalizer(client).normalize(source, datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI))

    assert event.subject == "OpenAI"
    assert event.canonical_url == "https://openai.com/codex"
    assert usage.input_tokens == 30
    assert "article_body" not in json.dumps(client.requests[0])


def test_minimax_normalizer_keeps_company_policy_position_and_feed_time_provenance() -> None:
    published_at = datetime(2026, 7, 15, 20, 0, tzinfo=SHANGHAI)
    reply = json.dumps(
        {
            "status": "new_event",
            "subject": "United States government",
            "object_name": "US frontier AI safety policy",
            "action": "policy_analysis",
            "core_change": "OpenAI describes emerging state and federal safety frameworks.",
            "event_at": published_at.isoformat(),
            "importance": "medium",
            "event_phase": "ongoing",
            "fact_type": "company_policy_position",
        }
    )
    client = FakeClient(reply)
    source = SourceItem(
        "openai-news",
        "Advancing AI safety through state and federal action",
        "https://openai.com/index/advancing-ai-safety-through-state-and-federal-action",
        published_at,
        "official",
    )

    event, _usage = MiniMaxNormalizer(client).normalize(
        source,
        datetime(2026, 7, 16, 1, 50, tzinfo=SHANGHAI),
    )

    assert event.subject == "OpenAI"
    assert event.fact_type == "company_policy_position"
    assert event.event_time_precision == "datetime"
    assert event.event_time_source == "rss"
    assert event.normalization_flags == ("feed_time_metadata", "publisher_subject_corrected")
    assert client.requests[0]["publisher_hint"] == "OpenAI"


def test_minimax_normalizer_accepts_json_after_provider_reasoning_preamble() -> None:
    reply = "<think>internal reasoning omitted</think>\n" + json.dumps(
        {
            "status": "new_event",
            "subject": "OpenAI",
            "object_name": "Codex",
            "action": "release",
            "core_change": "new coding capability",
            "event_at": "2026-07-14T06:00:00+08:00",
            "importance": "high",
            "event_phase": "released",
            "fact_type": "software_release",
        }
    )
    source = SourceItem("openai-news", "Codex update", "https://openai.com/codex", None, "official")

    event, _usage = MiniMaxNormalizer(FakeClient(reply)).normalize(
        source, datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI)
    )

    assert event.status == "new_event"


def test_minimax_normalizer_marks_missing_event_time_as_uncertain_without_using_publish_time() -> None:
    reply = json.dumps(
        {
            "status": "new_event",
            "subject": "OpenAI",
            "object_name": "Codex",
            "action": "release",
            "core_change": "new coding capability",
            "event_at": None,
            "importance": "high",
            "event_phase": "released",
            "fact_type": "software_release",
        }
    )
    published_at = datetime(2026, 7, 14, 6, 0, tzinfo=SHANGHAI)
    source = SourceItem("openai-news", "Codex update", "https://openai.com/codex", published_at, "official")

    event, _usage = MiniMaxNormalizer(FakeClient(reply)).normalize(source, datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI))

    assert event.event_at is None
    assert event.published_at == published_at
    assert event.status == "uncertain"


def test_minimax_normalizer_does_not_label_a_different_model_time_as_rss_time() -> None:
    reply = json.dumps(
        {
            "status": "new_event", "subject": "OpenAI", "object_name": "Codex",
            "action": "release", "core_change": "new coding capability",
            "event_at": "2026-07-14", "importance": "high",
            "event_phase": "released", "fact_type": "software_release",
        }
    )
    source = SourceItem(
        "openai-news", "Codex update", "https://openai.com/codex",
        datetime(2026, 7, 14, 18, 0, tzinfo=SHANGHAI), "official",
    )

    event, _usage = MiniMaxNormalizer(FakeClient(reply)).normalize(
        source, datetime(2026, 7, 14, 18, 20, tzinfo=SHANGHAI)
    )

    assert event.event_time_precision == "date"
    assert event.event_time_source == "inferred"
    assert "feed_time_metadata" not in event.normalization_flags


def test_minimax_normalizer_retries_once_after_an_incomplete_json_response() -> None:
    incomplete = json.dumps({"status": "new_event", "event_at": "2026-07-14T06:00:00+08:00"})
    complete = json.dumps(
        {
            "status": "new_event",
            "subject": "OpenAI",
            "object_name": "Codex",
            "action": "release",
            "core_change": "new coding capability",
            "event_at": "2026-07-14T06:00:00+08:00",
            "importance": "high",
            "event_phase": "released",
            "fact_type": "software_release",
        }
    )

    class SequencedClient:
        def __init__(self) -> None:
            self.contents = [incomplete, complete]
            self.requests: list[dict[str, object]] = []

        def complete(self, payload: dict[str, object]) -> ModelReply:
            self.requests.append(payload)
            return ModelReply(
                content=self.contents.pop(0),
                usage=ModelUsage("minimax", "MiniMax-M3", 30, 12),
            )

    client = SequencedClient()
    source = SourceItem("openai-news", "Codex update", "https://openai.com/codex", None, "official")

    event, usage = MiniMaxNormalizer(client).normalize(source, datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI))

    assert event.status == "new_event"
    assert len(client.requests) == 2
    assert event.normalization_flags == ("model_retry",)
    assert (usage.input_tokens, usage.output_tokens) == (60, 24)


def test_minimax_normalizer_retries_after_unsupported_importance() -> None:
    invalid = json.dumps(
        {
            "status": "new_event", "subject": "OpenAI", "object_name": "Codex",
            "action": "release", "core_change": "new coding capability",
            "event_at": "2026-07-14T06:00:00+08:00", "importance": "urgent",
            "event_phase": "released", "fact_type": "software_release",
        }
    )
    valid = json.dumps(
        {
            "status": "new_event", "subject": "OpenAI", "object_name": "Codex",
            "action": "release", "core_change": "new coding capability",
            "event_at": "2026-07-14T06:00:00+08:00", "importance": "high",
            "event_phase": "released", "fact_type": "software_release",
        }
    )

    class SequencedClient:
        def __init__(self) -> None:
            self.contents = [invalid, valid]

        def complete(self, _payload: dict[str, object]) -> ModelReply:
            return ModelReply(self.contents.pop(0), ModelUsage("minimax", "MiniMax-M3", 10, 5))

    source = SourceItem("openai-news", "Codex update", "https://openai.com/codex", None, "official")

    event, _usage = MiniMaxNormalizer(SequencedClient()).normalize(
        source, datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI)
    )

    assert event.importance == "high"
    assert event.normalization_flags == ("model_retry",)


def test_kimi_arbitrator_receives_at_most_three_compact_history_records() -> None:
    client = FakeClient(json.dumps({"status": "duplicate", "reason": "same official event"}))
    candidate = Event(
        "candidate", "uncertain", "OpenAI", "Codex", "release", "change", None, None,
        datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI), "https://openai.com/codex", "candidate",
        ("https://openai.com/codex",), "official", "high", "released",
    )
    history = [
        Event(str(index), "new_event", "OpenAI", "Codex", "release", "change", None, None,
              datetime(2026, 7, 13, 6, 20, tzinfo=SHANGHAI), f"https://example.com/{index}", str(index),
              (f"https://example.com/{index}",), "official", "high", "released")
        for index in range(4)
    ]

    result, _usage = KimiArbitrator(client).arbitrate(candidate, history)

    assert result == "duplicate"
    assert len(client.requests[0]["history"]) == 3


def test_openai_compatible_client_sends_structured_request_and_records_usage() -> None:
    observed: dict[str, object] = {}

    def request_json(url: str, headers: dict[str, str], payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        observed.update(url=url, headers=headers, payload=payload)
        return 200, {
            "id": "provider-request",
            "choices": [{"message": {"content": '{"status":"new_event"}'}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 5},
        }

    client = OpenAICompatibleClient("minimax", "https://api.example/v1", "MiniMax-M3", "secret-value", request_json)

    reply = client.complete({"task": "normalize_public_briefing_event", "source": {"title": "release"}})

    assert observed["url"] == "https://api.example/v1/chat/completions"
    assert observed["headers"] == {"Authorization": "Bearer secret-value", "Content-Type": "application/json"}
    assert observed["payload"]["model"] == "MiniMax-M3"
    assert reply.usage == ModelUsage("minimax", "MiniMax-M3", 8, 5, "provider-request")


def test_openai_compatible_client_merges_configured_request_options() -> None:
    observed: dict[str, object] = {}

    def request_json(url: str, headers: dict[str, str], payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        observed.update(url=url, headers=headers, payload=payload)
        return 200, {
            "id": "provider-request",
            "choices": [{"message": {"content": '{"status":"new_event"}'}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 5},
        }

    client = OpenAICompatibleClient(
        "minimax",
        "https://api.example/v1",
        "MiniMax-M3",
        "secret-value",
        request_json,
        request_options={
            "max_tokens": 512,
            "reasoning_split": True,
            "thinking": {"type": "disabled"},
        },
    )

    client.complete({"task": "normalize_public_briefing_event"})

    assert observed["payload"] == {
        "model": "MiniMax-M3",
        "messages": [
            {"role": "system", "content": "Return only valid JSON for the requested public-information task."},
            {"role": "user", "content": '{"task": "normalize_public_briefing_event"}'},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
        "reasoning_split": True,
        "thinking": {"type": "disabled"},
    }


def test_kimi_is_selected_only_for_high_priority_unresolved_events() -> None:
    high_uncertain = Event(
        "candidate", "uncertain", "OpenAI", "Codex", "release", "change", None, None,
        datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI), "https://openai.com/codex", "candidate",
        ("https://openai.com/codex",), "official", "high", "released",
    )
    low_uncertain = Event(
        "low", "uncertain", "OpenAI", "Codex", "release", "change", None, None,
        datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI), "https://example.com/low", "low",
        ("https://example.com/low",), "official", "low", "released",
    )

    assert should_use_kimi(high_uncertain, minimax_unresolved=True, affects_delivery=True)
    assert not should_use_kimi(low_uncertain, minimax_unresolved=True, affects_delivery=True)
    assert not should_use_kimi(high_uncertain, minimax_unresolved=False, affects_delivery=True)


def test_kimi_queue_is_limited_to_three_eligible_candidates_per_batch() -> None:
    candidates = [
        Event(
            f"candidate-{index}", "needs_semantic_review", "OpenAI", "Codex", "release", "change", None, None,
            datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI), f"https://example.com/{index}", str(index),
            (f"https://example.com/{index}",), "official", "high", "released",
        )
        for index in range(4)
    ]

    selected = select_kimi_candidates(candidates)

    assert [event.event_id for event in selected] == ["candidate-0", "candidate-1", "candidate-2"]


def test_kimi_failure_becomes_uncertain_without_retry() -> None:
    class FailingClient:
        def complete(self, _payload: dict[str, object]) -> ModelReply:
            raise RuntimeError("HTTP 429")

    candidate = Event(
        "candidate", "uncertain", "OpenAI", "Codex", "release", "change", None, None,
        datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI), "https://openai.com/codex", "candidate",
        ("https://openai.com/codex",), "official", "high", "released",
    )

    result, usage = KimiArbitrator(FailingClient()).arbitrate_safely(candidate, [])

    assert result == "uncertain"
    assert usage is None


def test_http_post_json_passes_authorization_without_logging_or_persisting_it() -> None:
    observed: dict[str, object] = {}

    class Response:
        status = 200

        def read(self) -> bytes:
            return b'{"id":"response"}'

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def opener(request: object, *, timeout: int) -> Response:
        observed["url"] = request.full_url  # type: ignore[attr-defined]
        observed["authorization"] = request.get_header("Authorization")  # type: ignore[attr-defined]
        observed["body"] = request.data  # type: ignore[attr-defined]
        assert timeout == 30
        return Response()

    status, payload = http_post_json(
        "https://api.example/v1/chat/completions",
        {"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        {"model": "test"},
        opener=opener,
    )

    assert status == 200
    assert payload == {"id": "response"}
    assert observed["authorization"] == "Bearer test-token"


def test_http_post_json_converts_network_timeout_to_runtime_error() -> None:
    def opener(_request: object, *, timeout: int) -> object:
        assert timeout == 30
        raise TimeoutError("read timed out")

    with pytest.raises(RuntimeError, match="network request failed"):
        http_post_json(
            "https://api.example/v1/chat/completions",
            {"Authorization": "Bearer test-token", "Content-Type": "application/json"},
            {"model": "test"},
            opener=opener,
        )
