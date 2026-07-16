from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence_briefing.public_pages import build_public_pages, render_review_page


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def manifest(*, kind: str = "morning", status: str = "success", batch_id: str | None = None) -> dict[str, object]:
    return {
        "batch_id": batch_id or f"{kind}-20260716T062000+0800",
        "kind": kind,
        "status": status,
        "trigger_type": "schedule",
        "coverage_mode": "scheduled_increment",
        "scheduled_for": "2026-07-16T06:20:00+08:00" if kind == "morning" else "2026-07-16T12:20:00+08:00",
        "actual_started_at": "2026-07-16T06:20:11+08:00",
        "started_at": "2026-07-16T06:20:11+08:00",
        "completed_at": "2026-07-16T06:21:30+08:00",
        "is_backfill": False,
        "is_zero_length_window": False,
        "data_range": {
            "start": "2026-07-15T13:10:00+08:00",
            "end": "2026-07-16T07:10:00+08:00",
            "lookback_start": "2026-07-15T07:10:00+08:00",
        },
        "source_commit_sha": "abc123def456",
        "workflow_run_id": "29460000000",
        "counts": {
            "input_events": 1,
            "duplicate_events": 0,
            "uncertain_events": 0,
            "selected_events": 1,
        },
        "errors": [],
    }


def event(marker: str = "PUBLIC-MARKER", *, url: str = "https://openai.com/example") -> dict[str, object]:
    return {
        "event_id": f"evt-{marker.casefold()}",
        "subject": "OpenAI",
        "object_name": "Codex",
        "action": "released",
        "core_change": marker,
        "event_at": "2026-07-16T05:00:00+08:00",
        "fact_type": "software_release",
        "event_time_precision": "datetime",
        "event_time_source": "rss",
        "canonical_url": url,
        "importance": "high",
        "event_phase": "released",
        "normalization_flags": ["feed_time_metadata"],
    }


def candidate_packet(marker: str = "PUBLIC-MARKER") -> dict[str, object]:
    item = event(marker)
    return {
        "sections": {
            "batch_state_and_range": {},
            "must_know": [item],
            "other_valid": [],
            "agentic_coding_and_toolchain": [item],
            "product_industry_policy": [],
            "uncertain_or_late": [],
            "quality_metrics": {},
        },
        "counts": {"input_events": 1, "duplicate_events": 0, "uncertain_events": 0, "selected_events": 1},
        "data_range": manifest()["data_range"],
        "duplicate_audit": [{"event_id": "evt-duplicate", "subject": "OpenAI", "canonical_url": "https://openai.com/dup"}],
        "normalization_audit": {
            "events": [{"event_id": item["event_id"], "flags": ["feed_time_metadata"]}],
            "events_with_flags": 1,
            "flag_counts": {"feed_time_metadata": 1},
        },
        "gpt_review_plan": {
            "mode": "bounded_second_pass_research",
            "state_boundary": "read_only",
            "search_budget": {"batch_total_max_queries": 12},
        },
    }


def prepare_current(root: Path, *, current_manifest: dict[str, object], marker: str = "PUBLIC-MARKER") -> None:
    current = root / "delivery/current"
    write_json(current / "manifest.json", current_manifest)
    write_json(current / "morning-candidates.json", candidate_packet(f"MORNING-{marker}"))
    write_json(current / "noon-candidates.json", candidate_packet(f"NOON-{marker}"))
    write_json(current / "recent-events.json", [event(f"RECENT-{marker}")])


def read_page(root: Path, relative: str) -> str:
    return (root / "docs" / relative / "index.html").read_text(encoding="utf-8")


def test_successful_morning_builds_ready_static_pages_with_all_review_sections(tmp_path: Path) -> None:
    current_manifest = manifest(kind="morning")
    prepare_current(tmp_path, current_manifest=current_manifest)

    outputs = build_public_pages(tmp_path)

    morning = read_page(tmp_path, "current/morning")
    status = read_page(tmp_path, "current/status")
    homepage = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    assert set(outputs) == {"index", "status", "morning", "noon", "style"}
    assert "review_status: ready" in morning
    assert "expected_kind: morning" in morning
    assert current_manifest["batch_id"] in morning
    assert current_manifest["source_commit_sha"] in morning
    for heading in (
        "Batch Status", "Data Range", "Must Know", "Other Valid",
        "Agentic Coding and Toolchain", "Product, Industry and Policy",
        "Uncertain or Late", "Duplicate Audit", "Normalization Audit",
        "GPT Review Plan", "Recent Successful Handoffs", "Original Public JSON Links",
    ):
        assert heading in morning
    for field in (
        "event_id", "subject", "object_name", "action", "core_change", "event_at",
        "fact_type", "event_time_precision", "event_time_source", "canonical_url",
        "importance", "event_phase", "normalization_flags",
    ):
        assert field in morning
    assert "evt-morning-public-marker" in morning
    assert "https://openai.com/example" in morning
    assert "feed_time_metadata" in morning
    assert "bounded_second_pass_research" in morning
    assert "batch_total_max_queries" in morning
    assert "review_input_type: manifest" in status
    assert "public_read_only: true" in status
    assert "credentials_required: false" in status
    assert "Personal Intelligence Briefing" in homepage
    assert "不需要登录或授权" in homepage


def test_successful_noon_is_ready_and_morning_does_not_read_stale_candidates(tmp_path: Path) -> None:
    prepare_current(tmp_path, current_manifest=manifest(kind="noon"), marker="CROSS-KIND")

    build_public_pages(tmp_path)

    noon = read_page(tmp_path, "current/noon")
    morning = read_page(tmp_path, "current/morning")
    assert "review_status: ready" in noon
    assert "NOON-CROSS-KIND" in noon
    assert "MORNING-CROSS-KIND" not in noon
    assert "review_status: unavailable" in morning
    assert "MORNING-CROSS-KIND" not in morning
    assert "RECENT-CROSS-KIND" not in morning


@pytest.mark.parametrize("status", ["failed", "partial"])
def test_non_success_manifest_renders_unavailable_without_old_candidates(tmp_path: Path, status: str) -> None:
    current_manifest = manifest(kind="morning", status=status)
    page = render_review_page(
        current_manifest,
        candidate_packet("STALE-CANDIDATE"),
        [event("STALE-RECENT")],
        expected_kind="morning",
    )

    assert "review_status: unavailable" in page
    assert f"status is {status}" in page
    assert "STALE-CANDIDATE" not in page
    assert "STALE-RECENT" not in page


def test_empty_candidates_and_recent_events_generate_a_ready_page(tmp_path: Path) -> None:
    current_manifest = manifest(kind="morning")
    current = tmp_path / "delivery/current"
    write_json(current / "manifest.json", current_manifest)
    write_json(current / "morning-candidates.json", {"sections": {}})
    write_json(current / "noon-candidates.json", {"sections": {}})
    write_json(current / "recent-events.json", [])

    build_public_pages(tmp_path)

    morning = read_page(tmp_path, "current/morning")
    assert "review_status: ready" in morning
    assert "No records." in morning


def test_missing_new_fields_are_compatible(tmp_path: Path) -> None:
    current_manifest = manifest(kind="morning")
    packet = candidate_packet()
    packet["sections"] = {
        "must_know": [{"event_id": "evt-legacy", "subject": "Legacy", "canonical_url": "https://example.com/legacy"}],
    }
    packet.pop("normalization_audit")
    packet.pop("gpt_review_plan")
    current = tmp_path / "delivery/current"
    write_json(current / "manifest.json", current_manifest)
    write_json(current / "morning-candidates.json", packet)
    write_json(current / "noon-candidates.json", {"sections": {}})
    write_json(current / "recent-events.json", [])

    build_public_pages(tmp_path)

    morning = read_page(tmp_path, "current/morning")
    assert "review_status: ready" in morning
    assert "evt-legacy" in morning
    assert "GPT Review Plan" in morning
    assert "Normalization Audit" in morning
    assert "No records." in morning


def test_untrusted_html_script_and_javascript_urls_are_never_executable(tmp_path: Path) -> None:
    current_manifest = manifest(kind="morning")
    packet = candidate_packet("<img src=x onerror=alert(1)><script>alert(2)</script>")
    packet["sections"]["must_know"][0]["canonical_url"] = "javascript:alert(3)"  # type: ignore[index]
    current = tmp_path / "delivery/current"
    write_json(current / "manifest.json", current_manifest)
    write_json(current / "morning-candidates.json", packet)
    write_json(current / "noon-candidates.json", {"sections": {}})
    write_json(current / "recent-events.json", [])

    build_public_pages(tmp_path)

    morning = read_page(tmp_path, "current/morning")
    assert "<script>" not in morning.casefold()
    assert "<img src=x" not in morning.casefold()
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in morning
    assert 'href="javascript:' not in morning.casefold()
    assert 'rel="noopener noreferrer external"' in morning


def test_public_pages_redact_secret_values_and_authorization_headers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "super-secret-environment-value"
    monkeypatch.setenv("KIMI_API_KEY", secret)
    marker = f"{secret} Authorization: Bearer bearer-secret sk-live-1234567890 github_pat_1234567890"
    prepare_current(tmp_path, current_manifest=manifest(kind="morning"), marker=marker)

    build_public_pages(tmp_path)

    public_html = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "docs").rglob("*.html"))
    assert secret not in public_html
    assert "Authorization" not in public_html
    assert "Bearer bearer-secret" not in public_html
    assert "sk-live-1234567890" not in public_html
    assert "github_pat_1234567890" not in public_html
    assert "[REDACTED]" in public_html


def test_pages_are_deterministic_utf8_server_rendered_and_cache_explicit(tmp_path: Path) -> None:
    current_manifest = manifest(kind="morning")
    prepare_current(tmp_path, current_manifest=current_manifest)

    build_public_pages(tmp_path)
    first = (tmp_path / "docs/current/morning/index.html").read_bytes()
    build_public_pages(tmp_path)
    second = (tmp_path / "docs/current/morning/index.html").read_bytes()

    decoded = first.decode("utf-8")
    assert first == second
    assert decoded.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in decoded
    assert 'http-equiv="Cache-Control"' in decoded
    assert 'name="robots" content="index,follow"' in decoded
    assert "<title>" in decoded
    assert 'name="description"' in decoded
    assert "<script" not in decoded.casefold()
    assert "<canvas" not in decoded.casefold()
    assert current_manifest["batch_id"] in decoded
    assert current_manifest["completed_at"] in decoded


def test_raw_links_include_batch_cache_buster_and_source_identity(tmp_path: Path) -> None:
    current_manifest = manifest(kind="morning", batch_id="morning-special+0800")
    prepare_current(tmp_path, current_manifest=current_manifest)

    build_public_pages(tmp_path)

    morning = read_page(tmp_path, "current/morning")
    assert "raw.githubusercontent.com/Ming-Sir-69/personal-intelligence-briefing/master/delivery/current/manifest.json?batch=morning-special%2B0800" in morning
    assert "morning-candidates.json?batch=morning-special%2B0800" in morning
    assert "recent-events.json?batch=morning-special%2B0800" in morning
    assert "abc123def456" in morning


@pytest.mark.parametrize("status", ["failed", "partial"])
def test_failed_or_partial_input_cannot_replace_an_existing_successful_public_snapshot(tmp_path: Path, status: str) -> None:
    prepare_current(tmp_path, current_manifest=manifest(kind="morning", status="success"), marker="LAST-GOOD")
    build_public_pages(tmp_path)
    snapshot = read_page(tmp_path, "current/morning")

    prepare_current(tmp_path, current_manifest=manifest(kind="morning", status=status), marker="NON-SUCCESS-NEW")
    build_public_pages(tmp_path)

    assert read_page(tmp_path, "current/morning") == snapshot
    assert "LAST-GOOD" in snapshot
    assert "NON-SUCCESS-NEW" not in snapshot


def test_all_generated_outputs_are_inside_docs_and_have_expected_paths(tmp_path: Path) -> None:
    prepare_current(tmp_path, current_manifest=manifest(kind="morning"))

    outputs = build_public_pages(tmp_path)

    assert outputs == {
        "index": tmp_path / "docs/index.html",
        "status": tmp_path / "docs/current/status/index.html",
        "morning": tmp_path / "docs/current/morning/index.html",
        "noon": tmp_path / "docs/current/noon/index.html",
        "style": tmp_path / "docs/assets/style.css",
    }
    assert (tmp_path / "docs/.nojekyll").exists()
