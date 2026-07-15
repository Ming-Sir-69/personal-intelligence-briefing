"""Deterministic history recall and first-pass event classification."""

from __future__ import annotations

from datetime import datetime

from .models import Event
from .storage import StateStore
from .time_window import age_band


PHASE_ORDER = {"preview": 1, "announced": 1, "beta": 2, "released": 3, "generally_available": 4}


def recall_history(store: StateStore, candidate: Event, now: datetime) -> list[Event]:
    recalled: list[Event] = []
    for event in store.successful_handoff_events():
        exact_match = event.canonical_url == candidate.canonical_url or event.fingerprint == candidate.fingerprint
        if exact_match:
            recalled.append(event)
            continue
        if candidate.event_at is None or event.event_at is None:
            continue
        if age_band(event.event_at, now) in {"hot", "warm"} and event.chain_key == candidate.chain_key:
            recalled.append(event)
    return recalled


def classify_candidate(candidate: Event, history: list[Event], now: datetime | None = None) -> str:
    for event in history:
        if event.canonical_url == candidate.canonical_url or event.fingerprint == candidate.fingerprint:
            return "duplicate"
    for event in history:
        if event.chain_key != candidate.chain_key:
            continue
        previous_phase = PHASE_ORDER.get(event.event_phase or "", 0)
        current_phase = PHASE_ORDER.get(candidate.event_phase or "", 0)
        if current_phase > previous_phase:
            return "substantive_update"
        if now and event.event_at and age_band(event.event_at, now) == "hot":
            return "needs_semantic_review"
        if event.core_change.strip().casefold() == candidate.core_change.strip().casefold():
            return "duplicate"
        return "uncertain"
    return "uncertain" if candidate.event_at is None else "new_event"
