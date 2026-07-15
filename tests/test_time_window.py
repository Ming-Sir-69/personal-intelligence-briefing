from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from intelligence_briefing.time_window import age_band, report_window


SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 7, 14, 7, 0, tzinfo=SHANGHAI)


def test_age_bands_are_non_overlapping_at_all_boundaries() -> None:
    assert age_band(NOW - timedelta(days=14), NOW) == "hot"
    assert age_band(NOW - timedelta(days=15), NOW) == "warm"
    assert age_band(NOW - timedelta(days=30), NOW) == "warm"
    assert age_band(NOW - timedelta(days=31), NOW) == "cold"
    assert age_band(NOW - timedelta(days=60), NOW) == "cold"
    assert age_band(NOW - timedelta(days=61), NOW) == "archive"
    assert age_band(NOW - timedelta(days=90), NOW) == "archive"
    assert age_band(NOW - timedelta(days=91), NOW) == "history"


def test_report_windows_never_claim_a_future_data_boundary() -> None:
    morning = report_window("morning", NOW)
    noon = report_window("noon", NOW)

    assert morning.end <= NOW
    assert noon.end <= NOW
    assert noon.start <= noon.end
    assert morning.lookback_start < morning.start
    assert morning.start.tzinfo == SHANGHAI


def test_scheduled_for_uses_github_action_start_time_not_data_window_end() -> None:
    now = datetime(2026, 7, 14, 18, 50, tzinfo=SHANGHAI)

    morning = report_window("morning", now)
    noon = report_window("noon", now)

    assert morning.scheduled_for == datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI)
    assert noon.scheduled_for == datetime(2026, 7, 14, 12, 20, tzinfo=SHANGHAI)
    assert morning.end == datetime(2026, 7, 14, 7, 10, tzinfo=SHANGHAI)
    assert noon.end == datetime(2026, 7, 14, 13, 10, tzinfo=SHANGHAI)
