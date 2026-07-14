"""Append-only public event state storage."""

from __future__ import annotations

import json
from pathlib import Path

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
