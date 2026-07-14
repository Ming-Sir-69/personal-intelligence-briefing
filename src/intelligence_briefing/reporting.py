"""Immutable candidate-packet delivery and stable current pointers."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Iterable

from .models import Batch, Event
from .time_window import report_window


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

    def write(self, batch: Batch, events: Iterable[Event], *, git_commit_sha: str, errors: tuple[str, ...] = ()) -> Path:
        effective_batch = replace(batch, errors=errors or batch.errors)
        archive = self.root / "delivery" / "archive" / f"{effective_batch.started_at:%Y-%m}" / effective_batch.batch_id
        archive.mkdir(parents=True, exist_ok=False)
        event_list = list(events)
        payload = self._candidate_payload(effective_batch, event_list)
        archive_path = archive.relative_to(self.root).as_posix()
        manifest = {
            "batch_id": effective_batch.batch_id,
            "kind": effective_batch.kind,
            "status": effective_batch.status,
            "started_at": effective_batch.started_at.isoformat(),
            "completed_at": effective_batch.completed_at.isoformat() if effective_batch.completed_at else None,
            "data_range": payload["data_range"],
            "archive_path": archive_path,
            "git_commit_sha": git_commit_sha,
            "counts": payload["counts"],
            "errors": list(effective_batch.errors),
            "model_usage": [usage.to_dict() for usage in effective_batch.model_usage],
        }
        self._write_json(archive / "candidates.json", payload)
        self._write_json(archive / "manifest.json", manifest)
        (archive / "preliminary.md").write_text(self._render_markdown(payload), encoding="utf-8")
        if effective_batch.status == "success":
            self._replace_current(effective_batch.kind, archive, manifest, payload)
        return archive

    def _candidate_payload(self, batch: Batch, events: list[Event]) -> dict[str, object]:
        sections: dict[str, object] = {key: [] for key in SECTION_KEYS}
        window = report_window(batch.kind, batch.started_at)
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
        sections["quality_metrics"] = {
            "input_events": len(events),
            "duplicate_events": sum(event.status == "duplicate" for event in events),
            "uncertain_events": sum(event.status == "uncertain" for event in events),
            "selected_events": len(valid),
        }
        return {"sections": sections, "counts": sections["quality_metrics"], "data_range": data_range}

    def _replace_current(self, kind: str, archive: Path, manifest: dict[str, object], payload: dict[str, object]) -> None:
        current = self.root / "delivery" / "current"
        current.mkdir(parents=True, exist_ok=True)
        self._write_json(current / "manifest.json", manifest)
        self._write_json(current / f"{kind}-candidates.json", payload)
        (current / f"{kind}-preliminary.md").write_text(self._render_markdown(payload), encoding="utf-8")
        recent = [
            item
            for key in ("must_know", "other_valid", "uncertain_or_late")
            for item in payload["sections"][key]  # type: ignore[index]
        ]
        self._write_json(current / "recent-events.json", recent)

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
        return "\n".join(lines) + "\n"
