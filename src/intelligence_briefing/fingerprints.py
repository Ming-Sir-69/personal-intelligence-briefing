"""Stable identifiers for public events without retaining source articles."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import re


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def event_fingerprint(subject: str, object_name: str, action: str, event_date: date | None, core_change: str) -> str:
    date_value = event_date.isoformat() if event_date else "unknown-date"
    payload = "|".join(_normalized(value) for value in (subject, object_name, action, date_value, core_change))
    return sha256(payload.encode("utf-8")).hexdigest()
