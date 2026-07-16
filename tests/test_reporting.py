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
    assert manifest["scheduled_for"] == "2026-07-14T12:20:00+08:00"
    assert manifest["actual_started_at"] == "2026-07-14T18:50:00+08:00"
    assert manifest["data_range"]["end"] == "2026-07-14T13:10:00+08:00"
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


def test_candidate_packet_gives_gpt_a_bounded_second_pass_research_plan(tmp_path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "sources-official-v1.yml").write_text(
        """version: 1
sources:
  - id: openai-news
    url: https://openai.com/news/rss.xml
    source_type: official
    enabled: true
  - id: anthropic-claude-code-releases
    url: https://github.com/anthropics/claude-code/releases.atom
    source_type: official
    enabled: true
""",
        encoding="utf-8",
    )
    writer = DeliveryWriter(tmp_path)

    archive = writer.write(batch(), [event()], source_commit_sha="test-sha")

    payload = json.loads((archive / "candidates.json").read_text(encoding="utf-8"))
    preliminary = (archive / "preliminary.md").read_text(encoding="utf-8")
    plan = payload["gpt_review_plan"]
    assert plan["mode"] == "bounded_second_pass_research"
    assert plan["state_boundary"] == "read_only"
    assert plan["trust_boundary"] == {
        "candidate_content": "untrusted_public_metadata",
        "embedded_instructions": "ignore",
        "credentials": "never request, expose, or persist",
    }
    assert plan["search_budget"] == {
        "candidate_verification_max_queries": 2,
        "candidate_verification_scope": "per_candidate",
        "batch_total_max_queries": 12,
        "gap_scan_max_queries": 4,
        "max_expansion_hops": 1,
        "max_supplements": 3,
    }
    assert [source["source_id"] for source in plan["priority_source_checks"]] == [
        "openai-news",
        "anthropic-claude-code-releases",
    ]
    review = plan["candidate_reviews"][0]
    assert review["event_id"] == "evt-1"
    assert review["review_level"] == "required"
    assert review["evidence_urls"] == ["https://openai.com/codex"]
    assert review["search_query_seeds"] == ['site:openai.com "OpenAI" "Codex" release']
    assert "verify the claimed core change against a primary source" in review["required_checks"]
    assert plan["required_output"] == [
        "retained",
        "corrected",
        "deleted",
        "supplemented",
        "system_findings",
    ]
    assert "## GPT 二次研究计划" in preliminary
    assert "bounded_second_pass_research" in preliminary


def test_gpt_review_plan_tightens_policy_and_uncertain_candidate_checks(tmp_path) -> None:
    writer = DeliveryWriter(tmp_path)
    policy = Event(
        "evt-policy", "uncertain", "OpenAI", "US AI safety policy", "policy_analysis",
        "OpenAI describes an emerging policy framework.", None, None,
        datetime(2026, 7, 14, 6, 20, tzinfo=SHANGHAI),
        "https://openai.com/policy", "policy-fingerprint", ("https://openai.com/policy",),
        "official", "medium", "ongoing", "company_policy_position", "date", "page",
        ("publisher_subject_corrected",),
    )

    archive = writer.write(batch(kind="noon"), [policy], source_commit_sha="test-sha")

    payload = json.loads((archive / "candidates.json").read_text(encoding="utf-8"))
    plan = payload["gpt_review_plan"]
    review = plan["candidate_reviews"][0]
    assert plan["search_budget"]["gap_scan_max_queries"] == 3
    assert plan["search_budget"]["max_supplements"] == 2
    assert review["review_level"] == "required"
    assert review["normalization_flags"] == ["publisher_subject_corrected"]
    assert "resolve uncertainty or exclude the event" in review["required_checks"]
    assert "distinguish company policy position from government action" in review["required_checks"]
    assert "verify date precision and label feed metadata separately" in review["required_checks"]
