"""Immutable candidate-packet delivery and stable current pointers."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from typing import Iterable

from .config import load_enabled_sources
from .gpt_review import build_gpt_review_plan
from .models import Batch, Event
from .time_window import ReportWindow, report_window


SECTION_KEYS = (
    "batch_state_and_range",
    "must_know",
    "other_valid",
    "agentic_coding_and_toolchain",
    "product_industry_policy",
    "uncertain_or_late",
    "quality_metrics",
)


class DeliveryWriter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write(
        self,
        batch: Batch,
        events: Iterable[Event],
        *,
        source_commit_sha: str,
        workflow_run_id: str | None = None,
        recent_events: Iterable[dict[str, object]] = (),
        errors: tuple[str, ...] = (),
        window: ReportWindow | None = None,
    ) -> Path:
        effective_batch = replace(batch, errors=errors or batch.errors)
        archive = self.root / "delivery" / "archive" / f"{effective_batch.started_at:%Y-%m}" / effective_batch.batch_id
        archive.mkdir(parents=True, exist_ok=False)
        event_list = list(events)
        payload = self._candidate_payload(effective_batch, event_list, window=window)
        archive_path = archive.relative_to(self.root).as_posix()
        manifest = {
            "batch_id": effective_batch.batch_id,
            "kind": effective_batch.kind,
            "status": effective_batch.status,
            "started_at": effective_batch.started_at.isoformat(),
            "completed_at": effective_batch.completed_at.isoformat() if effective_batch.completed_at else None,
            "data_range": payload["data_range"],
            "archive_path": archive_path,
            "schema_version": 2,
            "rules_version": "event-retention-v1",
            "source_commit_sha": source_commit_sha,
            "workflow_run_id": workflow_run_id,
            "counts": payload["counts"],
            "errors": list(effective_batch.errors),
            "model_usage": [usage.to_dict() for usage in effective_batch.model_usage],
            **self._run_context(effective_batch, window or report_window(effective_batch.kind, effective_batch.started_at)),
        }
        self._write_json(archive / "candidates.json", payload)
        self._write_json(archive / "manifest.json", manifest)
        (archive / "preliminary.md").write_text(self._render_markdown(payload), encoding="utf-8")
        if effective_batch.status == "success":
            self._replace_current(effective_batch.kind, archive, manifest, payload, recent_events)
        return archive

    def _candidate_payload(
        self,
        batch: Batch,
        events: list[Event],
        *,
        window: ReportWindow | None = None,
    ) -> dict[str, object]:
        sections: dict[str, object] = {key: [] for key in SECTION_KEYS}
        window = window or report_window(batch.kind, batch.started_at)
        data_range = {
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
            "lookback_start": window.lookback_start.isoformat(),
        }
        sections["batch_state_and_range"] = {
            "batch_id": batch.batch_id,
            "kind": batch.kind,
            "started_at": batch.started_at.isoformat(),
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "data_range": data_range,
            "trigger_type": batch.trigger_type,
        }
        valid = [event for event in events if event.status not in {"duplicate", "uncertain", "late_discovery"}]
        sections["must_know"] = [event.to_dict() for event in valid if event.importance == "high"]
        sections["other_valid"] = [event.to_dict() for event in valid if event.importance != "high"]
        sections["agentic_coding_and_toolchain"] = [
            event.to_dict() for event in valid if any(token in event.object_name.casefold() for token in ("codex", "claude code", "agent"))
        ]
        sections["product_industry_policy"] = [
            event.to_dict() for event in valid if any(token in event.action.casefold() for token in ("policy", "price", "access", "region"))
        ]
        sections["uncertain_or_late"] = [event.to_dict() for event in events if event.status in {"uncertain", "late_discovery"}]
        duplicate_audit = [
            {
                "event_id": event.event_id,
                "subject": event.subject,
                "object_name": event.object_name,
                "event_at": event.event_at.isoformat() if event.event_at else None,
                "canonical_url": event.canonical_url,
                "fingerprint": event.fingerprint,
            }
            for event in events
            if event.status == "duplicate"
        ]
        sections["quality_metrics"] = {
            "input_events": len(events),
            "duplicate_events": sum(event.status == "duplicate" for event in events),
            "uncertain_events": sum(event.status == "uncertain" for event in events),
            "selected_events": len(valid),
        }
        source_config = self.root / "config" / "sources-official-v1.yml"
        official_sources = load_enabled_sources(source_config) if source_config.exists() else []
        gpt_review_plan = build_gpt_review_plan(batch.kind, events, official_sources, data_range)
        flagged_events = [event for event in events if event.normalization_flags]
        flag_counts = Counter(flag for event in flagged_events for flag in event.normalization_flags)
        normalization_audit = {
            "events": [
                {"event_id": event.event_id, "flags": list(event.normalization_flags)}
                for event in flagged_events
            ],
            "events_with_flags": len(flagged_events),
            "flag_counts": dict(sorted(flag_counts.items())),
        }
        return {
            "sections": sections,
            "counts": sections["quality_metrics"],
            "data_range": data_range,
            "duplicate_audit": duplicate_audit,
            "normalization_audit": normalization_audit,
            "gpt_review_plan": gpt_review_plan,
        }

    @staticmethod
    def _run_context(batch: Batch, window: ReportWindow) -> dict[str, object]:
        is_zero_length_window = window.start >= window.end
        is_backfill = batch.trigger_type != "schedule"
        if batch.trigger_type == "schedule" and not is_zero_length_window:
            coverage_mode = "scheduled_increment"
        elif is_backfill:
            coverage_mode = "backfill"
        else:
            coverage_mode = "zero_length_scheduled_window"
        return {
            "trigger_type": batch.trigger_type,
            "coverage_mode": coverage_mode,
            "scheduled_for": (window.scheduled_for or window.end).isoformat(),
            "actual_started_at": batch.started_at.isoformat(),
            "is_backfill": is_backfill,
            "is_zero_length_window": is_zero_length_window,
        }

    def _replace_current(
        self,
        kind: str,
        archive: Path,
        manifest: dict[str, object],
        payload: dict[str, object],
        recent_events: Iterable[dict[str, object]],
    ) -> None:
        current = self.root / "delivery" / "current"
        current.mkdir(parents=True, exist_ok=True)
        self._write_json(current / "manifest.json", manifest)
        self._write_json(current / f"{kind}-candidates.json", payload)
        (current / f"{kind}-preliminary.md").write_text(self._render_markdown(payload), encoding="utf-8")
        self._write_json(current / "recent-events.json", list(recent_events))

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _render_markdown(payload: dict[str, object]) -> str:
        sections = payload["sections"]  # type: ignore[assignment]
        lines = ["# 候选简报初稿"]
        headings = {
            "batch_state_and_range": "批次状态与范围",
            "must_know": "必须关注",
            "other_valid": "其他有效新增",
            "agentic_coding_and_toolchain": "Agentic Coding 与工具链",
            "product_industry_policy": "产品、产业与政策影响",
            "uncertain_or_late": "不确定或迟到项",
            "quality_metrics": "去重与质量指标",
        }
        for key in SECTION_KEYS:
            lines.extend(("", f"## {headings[key]}", "", "```json", json.dumps(sections[key], ensure_ascii=False, indent=2), "```"))
        lines.extend((
            "",
            "## GPT 二次研究计划",
            "",
            "```json",
            json.dumps(payload["gpt_review_plan"], ensure_ascii=False, indent=2),
            "```",
        ))
        return "\n".join(lines) + "\n"
