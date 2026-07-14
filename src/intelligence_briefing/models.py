"""Public, serializable data contracts used by the briefing pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True)
class Event:
    event_id: str
    status: str
    subject: str
    object_name: str
    action: str
    core_change: str
    event_at: datetime | None
    published_at: datetime | None
    discovered_at: datetime
    canonical_url: str
    fingerprint: str
    source_urls: tuple[str, ...]
    source_type: str
    importance: str
    event_phase: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in ("event_at", "published_at", "discovered_at"):
            value = getattr(self, field)
            payload[field] = value.isoformat() if value else None
        payload["source_urls"] = list(self.source_urls)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Event":
        values = dict(payload)
        for field in ("event_at", "published_at", "discovered_at"):
            values[field] = _parse_datetime(values.get(field))
        values["source_urls"] = tuple(values.get("source_urls", ()))
        return cls(**values)

    @property
    def chain_key(self) -> tuple[str, str, str]:
        return tuple(value.strip().casefold() for value in (self.subject, self.object_name, self.action))


@dataclass(frozen=True)
class ModelUsage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelUsage":
        return cls(**payload)


@dataclass(frozen=True)
class SourceItem:
    source_id: str
    title: str
    url: str
    published_at: datetime | None
    source_type: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat() if self.published_at else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceItem":
        values = dict(payload)
        values["published_at"] = _parse_datetime(values.get("published_at"))
        return cls(**values)


@dataclass(frozen=True)
class Batch:
    batch_id: str
    kind: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    errors: tuple[str, ...]
    model_usage: tuple[ModelUsage, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "kind": self.kind,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "errors": list(self.errors),
            "model_usage": [usage.to_dict() for usage in self.model_usage],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Batch":
        values = dict(payload)
        values["started_at"] = _parse_datetime(values["started_at"])
        values["completed_at"] = _parse_datetime(values.get("completed_at"))
        values["errors"] = tuple(values.get("errors", ()))
        values["model_usage"] = tuple(ModelUsage.from_dict(item) for item in values.get("model_usage", ()))
        return cls(**values)
