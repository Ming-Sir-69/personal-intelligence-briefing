from datetime import datetime
import json
from zoneinfo import ZoneInfo

from intelligence_briefing.models import Batch, Event, ModelUsage
from intelligence_briefing.reporting import DeliveryWriter


SHANGHAI = ZoneInfo("Asia/Shanghai")


def event(status: str = "new_event") -> Event:
    now = datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI)
    return Event("evt-1", status, "OpenAI", "Codex", "release", "new coding capability", now, now, now,
                 "https://openai.com/codex", "fingerprint", ("https://openai.com/codex",), "official", "high", "released")


def batch(kind: str = "morning", status: str = "success", stamp: str = "062000") -> Batch:
    now = datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI)
    return Batch(f"{kind}-20260714T{stamp}+0800", kind, status, now, now, (), (ModelUsage("minimax", "M3", 20, 10),))


def test_successful_delivery_writes_immutable_archive_and_current_seven_sections(tmp_path) -> None:
    writer = DeliveryWriter(tmp_path)

    archive = writer.write(batch(), [event()], git_commit_sha="test-sha")

    payload = json.loads((archive / "candidates.json").read_text(encoding="utf-8"))
    current = json.loads((tmp_path / "delivery/current/manifest.json").read_text(encoding="utf-8"))
    assert set(payload["sections"]) == {
        "batch_state_and_range", "must_know", "other_valid", "agentic_coding_and_toolchain",
        "product_industry_policy", "uncertain_or_late", "quality_metrics",
    }
    assert current["git_commit_sha"] == "test-sha"
    assert current["data_range"]["start"] < current["data_range"]["end"]
    assert (tmp_path / "delivery/current/morning-candidates.json").exists()


def test_failed_delivery_keeps_the_last_successful_current_packet(tmp_path) -> None:
    writer = DeliveryWriter(tmp_path)
    writer.write(batch(), [event()], git_commit_sha="good-sha")
    writer.write(batch(status="failed", stamp="122000"), [], git_commit_sha="bad-sha", errors=("collector timeout",))

    current = json.loads((tmp_path / "delivery/current/manifest.json").read_text(encoding="utf-8"))
    failed_archive = tmp_path / "delivery/archive/2026-07/morning-20260714T122000+0800"
    assert current["git_commit_sha"] == "good-sha"
    assert json.loads((failed_archive / "manifest.json").read_text(encoding="utf-8"))["status"] == "failed"
