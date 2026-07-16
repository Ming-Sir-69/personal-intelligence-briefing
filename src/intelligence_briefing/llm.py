"""Provider-neutral structured model routes with no credential persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Callable, Protocol
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .fingerprints import event_fingerprint
from .models import Event, ModelUsage, SourceItem
from .url_normalization import normalize_url


FACT_TYPES = {
    "official_government_action",
    "company_policy_position",
    "research_result",
    "product_release",
    "software_release",
    "security_disclosure",
    "other",
}

IMPORTANCE_LEVELS = {"high", "medium", "low", "minor"}

MAX_PROVIDER_RESPONSE_BYTES = 2_000_000
MODEL_FIELD_LIMITS = {
    "status": 64,
    "subject": 200,
    "object_name": 300,
    "action": 120,
    "core_change": 1_200,
    "event_phase": 120,
}

PUBLISHER_HINTS = {
    "openai-news": "OpenAI",
    "openai-codex-releases": "OpenAI",
    "anthropic-claude-code-releases": "Anthropic",
}


def http_post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    *,
    opener: Callable[..., object] = urlopen,
    timeout_seconds: int = 30,
) -> tuple[int, dict[str, object]]:
    parsed_url = urlsplit(url.strip())
    if parsed_url.scheme.casefold() != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
        raise ValueError("model API must use an HTTPS URL without embedded credentials")
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    try:
        with opener(request, timeout=timeout_seconds) as response:  # type: ignore[attr-defined]
            body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)  # type: ignore[attr-defined]
            if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
                raise RuntimeError("provider response exceeds safety limit")
            return int(response.status), json.loads(body)
    except HTTPError as error:
        body_bytes = error.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        if len(body_bytes) > MAX_PROVIDER_RESPONSE_BYTES:
            return error.code, {"error": {"message": "provider response exceeds safety limit"}}
        body = body_bytes.decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, {"error": {"message": body}}
    except OSError as error:
        raise RuntimeError("network request failed") from error


@dataclass(frozen=True)
class ModelReply:
    content: str
    usage: ModelUsage
    request_id: str | None = None


class StructuredClient(Protocol):
    def complete(self, payload: dict[str, object]) -> ModelReply: ...


class OpenAICompatibleClient:
    """Thin API adapter; secrets stay only in process memory."""

    def __init__(
        self,
        provider: str,
        base_url: str,
        model: str,
        api_key: str,
        request_json: Callable[[str, dict[str, str], dict[str, object]], tuple[int, dict[str, object]]],
        request_options: dict[str, object] | None = None,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self._request_json = request_json
        self._request_options = request_options or {}

    def complete(self, payload: dict[str, object]) -> ModelReply:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON for the requested public-information task."},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0.1,
        }
        body.update(self._request_options)
        status, response = self._request_json(
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            body,
        )
        if status >= 400:
            raise RuntimeError(f"{self.provider} request failed with HTTP {status}")
        try:
            content = response["choices"][0]["message"]["content"]
            usage = response.get("usage", {})
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(f"{self.provider} response is not a chat completion") from error
        return ModelReply(
            content=str(content),
            usage=ModelUsage(
                provider=self.provider,
                model=self.model,
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                request_id=str(response.get("id")) if response.get("id") else None,
            ),
            request_id=str(response.get("id")) if response.get("id") else None,
        )


def _event_datetime(value: object, timezone: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone)  # type: ignore[arg-type]


def _publisher_hint(source: SourceItem) -> str:
    if source.source_id in PUBLISHER_HINTS:
        return PUBLISHER_HINTS[source.source_id]
    return urlsplit(source.url).hostname or source.source_id


def _event_time_precision(value: object, parsed: datetime | None) -> str:
    if parsed is None or not isinstance(value, str):
        return "unknown"
    return "date" if len(value.strip()) == 10 else "datetime"


class MiniMaxNormalizer:
    def __init__(self, client: StructuredClient) -> None:
        self.client = client

    def normalize(self, source: SourceItem, discovered_at: datetime) -> tuple[Event, ModelUsage]:
        publisher_hint = _publisher_hint(source)
        request = {
            "task": "normalize_public_briefing_event",
            "required_fields": [
                "status", "subject", "object_name", "action", "core_change", "event_at",
                "importance", "event_phase", "fact_type",
            ],
            "source": source.to_dict(),
            "publisher_hint": publisher_hint,
            "allowed_fact_types": sorted(FACT_TYPES),
            "constraints": [
                "do not invent an official date",
                "do not request or return article body",
                "a company-authored policy or analysis article is company_policy_position unless it directly reports a sourced government action",
                "for company_policy_position use publisher_hint as subject, not the government being discussed",
                "an RSS or Atom timestamp is publication metadata, not proof of the exact event occurrence time",
            ],
        }
        required = {"status", "subject", "object_name", "action", "core_change", "importance", "fact_type"}
        replies: list[ModelReply] = []
        for attempt in range(2):
            reply = self.client.complete(request)
            replies.append(reply)
            try:
                payload = _load_json_object(reply.content)
                missing = required - payload.keys()
                if missing:
                    raise ValueError(f"model response missing fields: {sorted(missing)}")
                if not isinstance(payload["fact_type"], str) or payload["fact_type"] not in FACT_TYPES:
                    raise ValueError("model response returned an unsupported fact_type")
                if not isinstance(payload["importance"], str) or payload["importance"] not in IMPORTANCE_LEVELS:
                    raise ValueError("model response returned an unsupported importance")
                for field, limit in MODEL_FIELD_LIMITS.items():
                    value = payload.get(field, "")
                    if not isinstance(value, str) or (field != "event_phase" and not value.strip()):
                        raise ValueError(f"model response returned an empty {field}")
                    if len(value) > limit:
                        raise ValueError(f"model response exceeded the {field} length limit")
            except (ValueError, json.JSONDecodeError):
                if attempt == 1:
                    raise
                continue
            break
        else:  # pragma: no cover - the final attempt always raises or breaks
            raise RuntimeError("normalization retry loop did not complete")
        raw_event_at = payload.get("event_at")
        event_at = _event_datetime(raw_event_at, discovered_at.tzinfo)
        fact_type = str(payload["fact_type"])
        subject = publisher_hint if fact_type == "company_policy_position" else str(payload["subject"])
        feed_time_matches = bool(event_at and source.published_at and event_at == source.published_at)
        normalization_flags: list[str] = []
        if len(replies) > 1:
            normalization_flags.append("model_retry")
        if feed_time_matches:
            normalization_flags.append("feed_time_metadata")
        if fact_type == "company_policy_position" and str(payload["subject"]).strip() != publisher_hint:
            normalization_flags.append("publisher_subject_corrected")
        fingerprint = event_fingerprint(
            subject,
            str(payload["object_name"]),
            str(payload["action"]),
            event_at.date() if event_at else None,
            str(payload["core_change"]),
        )
        event_id = f"evt-{sha256((fingerprint + source.url).encode()).hexdigest()[:16]}"
        return (
            Event(
                event_id=event_id,
                status=str(payload["status"]) if event_at else "uncertain",
                subject=subject,
                object_name=str(payload["object_name"]),
                action=str(payload["action"]),
                core_change=str(payload["core_change"]),
                event_at=event_at,
                published_at=source.published_at,
                discovered_at=discovered_at,
                canonical_url=normalize_url(source.url),
                fingerprint=fingerprint,
                source_urls=(normalize_url(source.url),),
                source_type=source.source_type,
                importance=str(payload["importance"]),
                event_phase=str(payload.get("event_phase") or ""),
                fact_type=fact_type,
                event_time_precision=_event_time_precision(raw_event_at, event_at),
                event_time_source="rss" if feed_time_matches else "inferred" if event_at else "unknown",
                normalization_flags=tuple(normalization_flags),
            ),
            ModelUsage(
                provider=reply.usage.provider,
                model=reply.usage.model,
                input_tokens=sum(item.usage.input_tokens for item in replies),
                output_tokens=sum(item.usage.output_tokens for item in replies),
                request_id=reply.usage.request_id,
            ),
        )


class KimiArbitrator:
    def __init__(self, client: StructuredClient) -> None:
        self.client = client

    def arbitrate(self, candidate: Event, history: list[Event]) -> tuple[str, ModelUsage]:
        compact_history = [
            {
                "event_id": event.event_id,
                "subject": event.subject,
                "object_name": event.object_name,
                "action": event.action,
                "event_at": event.event_at.isoformat() if event.event_at else None,
                "core_change": event.core_change,
                "status": event.status,
            }
            for event in history[:3]
        ]
        reply = self.client.complete(
            {
                "task": "arbitrate_briefing_event",
                "candidate": candidate.to_dict(),
                "history": compact_history,
                "allowed_statuses": ["new_event", "duplicate", "substantive_update", "late_discovery", "uncertain"],
            }
        )
        status = _load_json_object(reply.content).get("status")
        if status not in {"new_event", "duplicate", "substantive_update", "late_discovery", "uncertain"}:
            raise ValueError("model arbitration returned an unsupported status")
        return status, reply.usage

    def arbitrate_safely(self, candidate: Event, history: list[Event]) -> tuple[str, ModelUsage | None]:
        try:
            return self.arbitrate(candidate, history)
        except (RuntimeError, ValueError, json.JSONDecodeError):
            return "uncertain", None


def should_use_kimi(candidate: Event, *, minimax_unresolved: bool, affects_delivery: bool) -> bool:
    return candidate.importance == "high" and minimax_unresolved and affects_delivery


def select_kimi_candidates(candidates: list[Event]) -> list[Event]:
    return [
        candidate
        for candidate in candidates
        if candidate.status == "needs_semantic_review" and should_use_kimi(candidate, minimax_unresolved=True, affects_delivery=True)
    ][:3]


def _load_json_object(content: str) -> dict[str, object]:
    """Accept provider preambles while still rejecting non-object responses."""
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("no JSON object found", content, 0)
    payload = json.loads(content[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model response must be a JSON object")
    return payload
