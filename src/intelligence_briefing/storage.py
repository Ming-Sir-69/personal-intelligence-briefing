"""Append-only public event state storage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Batch, Event


class StateStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def events_dir(self) -> Path:
        return self.root / "data" / "events"

    @property
    def permanent_identifiers_path(self) -> Path:
        return self.root / "data" / "permanent-identifiers.json"

    @property
    def source_watermarks_path(self) -> Path:
        return self.root / "data" / "source-watermarks.json"

    def last_successful_completed_at(self) -> datetime | None:
        """Return the durable boundary from the last fully successful batch."""
        if not self.source_watermarks_path.exists():
            return None
        payload = json.loads(self.source_watermarks_path.read_text(encoding="utf-8"))
        value = payload.get("last_successful_batch", {}).get("completed_at")
        return datetime.fromisoformat(value) if isinstance(value, str) else None

    def write_successful_watermark(self, batch: Batch) -> Path:
        if batch.status != "success" or batch.completed_at is None:
            raise ValueError("only completed successful batches may advance the watermark")
        self.source_watermarks_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "last_successful_batch": {
                "batch_id": batch.batch_id,
                "completed_at": batch.completed_at.isoformat(),
            },
        }
        self.source_watermarks_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.source_watermarks_path

    def append_event(self, event: Event) -> Path:
        self.events_dir.mkdir(parents=True, exist_ok=True)
        destination = self.events_dir / f"events-{event.discovered_at:%Y-%m}.jsonl"
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        self._merge_permanent_identifiers(event)
        return destination

    def all_events(self) -> list[Event]:
        events: list[Event] = []
        for path in sorted(self.events_dir.glob("events-*.jsonl")) if self.events_dir.exists() else []:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(Event.from_dict(json.loads(line)))
        return events

    def write_run(self, batch: Batch) -> Path:
        destination = self.root / "data" / "runs" / f"run-{batch.batch_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(batch.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return destination

    def append_gpt_handoffs(self, batch: Batch, events: Iterable[Event]) -> Path:
        """Record only events that reached a successful GitHub candidate packet."""
        submitted_at_datetime = batch.completed_at or batch.started_at
        destination = self.root / "data" / "gpt-handoffs" / f"handoffs-{submitted_at_datetime:%Y-%m}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        submitted_at = submitted_at_datetime.isoformat()
        with destination.open("a", encoding="utf-8") as handle:
            for event in events:
                if event.status == "duplicate":
                    continue
                payload = event.to_dict()
                payload.update({"batch_id": batch.batch_id, "submitted_to_gpt_at": submitted_at})
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
        return destination

    def recent_gpt_handoffs(self, now: object, days: int = 30) -> list[dict[str, object]]:
        from datetime import timedelta

        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        cutoff = now - timedelta(days=days)
        latest_by_event: dict[str, dict[str, object]] = {}
        directory = self.root / "data" / "gpt-handoffs"
        for path in sorted(directory.glob("handoffs-*.jsonl")) if directory.exists() else []:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                submitted_at = payload.get("submitted_to_gpt_at")
                if not isinstance(submitted_at, str):
                    continue
                if datetime.fromisoformat(submitted_at) < cutoff:
                    continue
                event_id = str(payload["event_id"])
                latest_by_event[event_id] = payload
        return sorted(latest_by_event.values(), key=lambda item: str(item["submitted_to_gpt_at"]), reverse=True)

    def rebuild_active_events(self, now: object) -> list[Event]:
        from datetime import datetime
        from .time_window import age_band

        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        active = [event for event in self.all_events() if age_band(event.event_at, now) in {"hot", "warm"}]
        destination = self.root / "data" / "active-events.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([event.to_dict() for event in active], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return active

    def _merge_permanent_identifiers(self, event: Event) -> None:
        self.permanent_identifiers_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, str] = {}
        if self.permanent_identifiers_path.exists():
            existing = json.loads(self.permanent_identifiers_path.read_text(encoding="utf-8"))
        for key in {event.event_id, event.canonical_url, event.fingerprint}:
            existing[key] = event.event_id
        self.permanent_identifiers_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
