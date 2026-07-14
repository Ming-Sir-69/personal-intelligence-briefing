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


def test_report_windows_use_china_time_and_allow_discovery_overlap() -> None:
    morning = report_window("morning", NOW)
    noon = report_window("noon", NOW)

    assert morning.end <= NOW
    assert noon.end > morning.end
    assert morning.lookback_start < morning.start
    assert morning.start.tzinfo == SHANGHAI
