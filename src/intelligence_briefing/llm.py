"""Provider-neutral structured model routes with no credential persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Callable, Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .fingerprints import event_fingerprint
from .models import Event, ModelUsage, SourceItem
from .url_normalization import normalize_url


def http_post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    *,
    opener: Callable[..., object] = urlopen,
) -> tuple[int, dict[str, object]]:
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    try:
        with opener(request, timeout=30) as response:  # type: ignore[attr-defined]
            return int(response.status), json.loads(response.read())  # type: ignore[attr-defined]
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, {"error": {"message": body}}


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
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self._request_json = request_json

    def complete(self, payload: dict[str, object]) -> ModelReply:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON for the requested public-information task."},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0.1,
        }
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


class MiniMaxNormalizer:
    def __init__(self, client: StructuredClient) -> None:
        self.client = client

    def normalize(self, source: SourceItem, discovered_at: datetime) -> tuple[Event, ModelUsage]:
        request = {
            "task": "normalize_public_briefing_event",
            "required_fields": ["status", "subject", "object_name", "action", "core_change", "event_at", "importance", "event_phase"],
            "source": source.to_dict(),
            "constraints": ["do not invent an official date", "do not request or return article body"],
        }
        reply = self.client.complete(request)
        payload = json.loads(reply.content)
        required = {"status", "subject", "object_name", "action", "core_change", "importance"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"model response missing fields: {sorted(missing)}")
        event_at = _event_datetime(payload.get("event_at"), discovered_at.tzinfo)
        fingerprint = event_fingerprint(
            str(payload["subject"]),
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
                subject=str(payload["subject"]),
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
            ),
            reply.usage,
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
        status = json.loads(reply.content).get("status")
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
