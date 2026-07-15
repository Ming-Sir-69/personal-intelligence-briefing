"""Timezone-aware report and media-echo window helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class ReportWindow:
    kind: str
    start: datetime
    end: datetime
    lookback_start: datetime


def age_band(event_at: datetime | None, now: datetime) -> str:
    if event_at is None:
        return "unknown"
    local_event = event_at.astimezone(SHANGHAI).date()
    local_now = now.astimezone(SHANGHAI).date()
    age = max(0, (local_now - local_event).days)
    if age <= 14:
        return "hot"
    if age <= 30:
        return "warm"
    if age <= 60:
        return "cold"
    if age <= 90:
        return "archive"
    return "history"


def report_window(
    kind: str,
    now: datetime,
    overlap: timedelta = timedelta(hours=6),
    *,
    previous_success_at: datetime | None = None,
) -> ReportWindow:
    """Return a report boundary with discovery overlap.

    The first successful batch uses the planned delivery cadence.  Afterwards,
    the previous successful batch is the authoritative boundary.  This lets a
    delayed GitHub Actions run catch up without leaving a gap between batches.
    """
    local_now = now.astimezone(SHANGHAI)
    if kind == "morning":
        planned_end = local_now.replace(hour=7, minute=10, second=0, microsecond=0)
        planned_start = (planned_end - timedelta(days=1)).replace(hour=13, minute=10)
    elif kind == "noon":
        planned_end = local_now.replace(hour=13, minute=10, second=0, microsecond=0)
        planned_start = local_now.replace(hour=7, minute=10, second=0, microsecond=0)
    else:
        raise ValueError(f"unsupported batch kind: {kind}")
    end = min(planned_end, local_now)
    start = min(planned_start, end)
    if previous_success_at is not None:
        previous_local = previous_success_at.astimezone(SHANGHAI)
        start = min(previous_local, end)
    return ReportWindow(kind=kind, start=start, end=end, lookback_start=start - overlap)
