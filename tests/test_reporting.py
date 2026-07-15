from datetime import datetime
import json
from zoneinfo import ZoneInfo

from intelligence_briefing.models import Batch, Event, ModelUsage
from intelligence_briefing.reporting import DeliveryWriter
from intelligence_briefing.time_window import report_window


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

    archive = writer.write(batch(), [event()], source_commit_sha="test-sha")

    payload = json.loads((archive / "candidates.json").read_text(encoding="utf-8"))
    current = json.loads((tmp_path / "delivery/current/manifest.json").read_text(encoding="utf-8"))
    assert set(payload["sections"]) == {
        "batch_state_and_range", "must_know", "other_valid", "agentic_coding_and_toolchain",
        "product_industry_policy", "uncertain_or_late", "quality_metrics",
    }
    assert current["source_commit_sha"] == "test-sha"
    assert current["data_range"]["start"] < current["data_range"]["end"]
    assert (tmp_path / "delivery/current/morning-candidates.json").exists()


def test_manifest_marks_manual_zero_length_window_as_backfill(tmp_path) -> None:
    writer = DeliveryWriter(tmp_path)
    zero_window_batch = Batch(
        "noon-20260714T185000+0800", "noon", "success",
        datetime(2026, 7, 14, 18, 50, tzinfo=SHANGHAI),
        datetime(2026, 7, 14, 18, 50, tzinfo=SHANGHAI), (), (),
        trigger_type="workflow_dispatch",
    )

    archive = writer.write(
        zero_window_batch,
        [event()],
        source_commit_sha="test-sha",
        window=report_window(
            "noon",
            zero_window_batch.started_at,
            previous_success_at=datetime(2026, 7, 14, 18, 47, tzinfo=SHANGHAI),
        ),
    )

    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["trigger_type"] == "workflow_dispatch"
    assert manifest["coverage_mode"] == "backfill"
    assert manifest["is_backfill"] is True
    assert manifest["is_zero_length_window"] is True


def test_candidate_payload_keeps_a_minimal_audit_record_for_suppressed_duplicates(tmp_path) -> None:
    writer = DeliveryWriter(tmp_path)

    archive = writer.write(batch(), [event(status="duplicate")], source_commit_sha="test-sha")

    payload = json.loads((archive / "candidates.json").read_text(encoding="utf-8"))
    audit = payload["duplicate_audit"]
    assert audit == [{
        "canonical_url": "https://openai.com/codex",
        "event_id": "evt-1",
        "event_at": "2026-07-14T06:20:00+08:00",
        "fingerprint": "fingerprint",
        "object_name": "Codex",
        "subject": "OpenAI",
    }]


def test_failed_delivery_keeps_the_last_successful_current_packet(tmp_path) -> None:
    writer = DeliveryWriter(tmp_path)
    writer.write(batch(), [event()], source_commit_sha="good-sha")
    writer.write(batch(status="failed", stamp="122000"), [], source_commit_sha="bad-sha", errors=("collector timeout",))

    current = json.loads((tmp_path / "delivery/current/manifest.json").read_text(encoding="utf-8"))
    failed_archive = tmp_path / "delivery/archive/2026-07/morning-20260714T122000+0800"
    assert current["source_commit_sha"] == "good-sha"
    assert json.loads((failed_archive / "manifest.json").read_text(encoding="utf-8"))["status"] == "failed"
