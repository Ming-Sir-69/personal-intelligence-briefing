"""Deterministic, server-rendered public review pages for current delivery JSON."""

from __future__ import annotations

from html import escape
import json
import os
from pathlib import Path
import re
from typing import Mapping, Sequence
from urllib.parse import quote, urlsplit


DEFAULT_REPOSITORY = "Ming-Sir-69/personal-intelligence-briefing"
DEFAULT_BRANCH = "master"
SITE_PREFIX = "/personal-intelligence-briefing"
EVENT_FIELDS = (
    "event_id",
    "subject",
    "object_name",
    "action",
    "core_change",
    "event_at",
    "fact_type",
    "event_time_precision",
    "event_time_source",
    "canonical_url",
    "importance",
    "event_phase",
    "normalization_flags",
)
SECTION_HEADINGS = (
    ("must_know", "Must Know"),
    ("other_valid", "Other Valid"),
    ("agentic_coding_and_toolchain", "Agentic Coding and Toolchain"),
    ("product_industry_policy", "Product, Industry and Policy"),
    ("uncertain_or_late", "Uncertain or Late"),
)
SECRET_ENV_NAME = re.compile(r"(?:API_KEY|TOKEN|SECRET|PASSWORD|AUTHORIZATION)", re.IGNORECASE)
SENSITIVE_PATTERNS = (
    re.compile(r"\bAuthorization\b\s*[:=]\s*(?:Bearer\s+)?[^\s<>'\"]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}", re.IGNORECASE),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}", re.IGNORECASE),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}", re.IGNORECASE),
)


def build_public_pages(
    root: Path,
    *,
    output_dir: Path | None = None,
    repository: str = DEFAULT_REPOSITORY,
    branch: str = DEFAULT_BRANCH,
) -> dict[str, Path]:
    """Build a deterministic public snapshot from delivery/current JSON."""
    root = Path(root)
    output = output_dir or root / "docs"
    paths = _output_paths(output)
    manifest_path = root / "delivery/current/manifest.json"
    manifest = _read_json(manifest_path, default={})

    if manifest.get("status") != "success" and paths["status"].exists():
        return paths

    recent_path = root / "delivery/current/recent-events.json"
    pages: dict[str, str] = {
        "index": render_homepage(manifest),
        "status": render_status_page(manifest, repository=repository, branch=branch),
    }
    for kind in ("morning", "noon"):
        ready = manifest.get("status") == "success" and manifest.get("kind") == kind
        candidates = (
            _read_json(root / f"delivery/current/{kind}-candidates.json", default={})
            if ready
            else {}
        )
        recent = _read_json(recent_path, default=[]) if ready else []
        pages[kind] = render_review_page(
            manifest,
            candidates if isinstance(candidates, Mapping) else {},
            recent if isinstance(recent, list) else [],
            expected_kind=kind,
            repository=repository,
            branch=branch,
        )

    pages["style"] = _stylesheet()
    _validate_public_outputs(pages)
    for name, content in pages.items():
        _atomic_write(paths[name], content)
    (output / ".nojekyll").parent.mkdir(parents=True, exist_ok=True)
    (output / ".nojekyll").touch(exist_ok=True)
    return paths


def render_homepage(manifest: Mapping[str, object]) -> str:
    batch_id = _display(manifest.get("batch_id"))
    status = _display(manifest.get("status"))
    generated_at = _generated_at(manifest)
    body = f"""
<section aria-labelledby="overview-heading">
  <h1 id="overview-heading">Personal Intelligence Briefing</h1>
  <p>这是 Personal Intelligence Briefing 的公开只读审核入口，不需要登录或授权。</p>
  <nav aria-label="审核入口">
    <ul>
      <li><a href="{SITE_PREFIX}/current/status/">当前状态</a></li>
      <li><a href="{SITE_PREFIX}/current/morning/">晨间审核入口</a></li>
      <li><a href="{SITE_PREFIX}/current/noon/">午间审核入口</a></li>
    </ul>
  </nav>
</section>
<section aria-labelledby="current-heading">
  <h2 id="current-heading">当前公开状态</h2>
  <dl class="metadata">
    <dt>batch_id</dt><dd>{batch_id}</dd>
    <dt>status</dt><dd>{status}</dd>
    <dt>generated_at</dt><dd>{_display(generated_at)}</dd>
  </dl>
  <p>请以下游页面正文中的 batch_id、generated_at 与 source_commit_sha 判断新鲜度。</p>
</section>"""
    return _document("Personal Intelligence Briefing｜公开审核入口", "公开、只读、无需授权的跨平台审核入口。", body)


def render_status_page(
    manifest: Mapping[str, object],
    *,
    repository: str = DEFAULT_REPOSITORY,
    branch: str = DEFAULT_BRANCH,
) -> str:
    batch_id = str(manifest.get("batch_id") or "unavailable")
    summary = "\n".join((
        "review_input_type: manifest",
        "public_read_only: true",
        "credentials_required: false",
        f"batch_id: {_plain(batch_id)}",
        f"generated_at: {_plain(_generated_at(manifest))}",
        f"source_commit_sha: {_plain(manifest.get('source_commit_sha'))}",
    ))
    fields = (
        "batch_id", "kind", "status", "trigger_type", "coverage_mode", "scheduled_for",
        "actual_started_at", "completed_at", "is_backfill", "is_zero_length_window",
        "source_commit_sha", "workflow_run_id",
    )
    rows = [(field, manifest.get(field)) for field in fields]
    data_range = manifest.get("data_range") if isinstance(manifest.get("data_range"), Mapping) else {}
    rows.extend((f"data_range.{key}", data_range.get(key)) for key in ("start", "end", "lookback_start"))
    rows.extend((("counts", manifest.get("counts")), ("errors", manifest.get("errors"))))
    raw_links = _raw_links(repository, branch, batch_id, ("manifest.json",))
    body = f"""
<h1>Current Batch Status</h1>
<pre class="machine-summary">{_safe(summary)}</pre>
<p>generated_at: {_display(_generated_at(manifest))}</p>
{_definition_table(rows)}
<section aria-labelledby="status-json-heading">
  <h2 id="status-json-heading">Original Public JSON Links</h2>
  {_link_list(raw_links)}
</section>"""
    return _document("Current Status｜Personal Intelligence Briefing", "当前成功批次的公开只读manifest状态。", body)


def render_review_page(
    manifest: Mapping[str, object],
    candidates: Mapping[str, object],
    recent_events: Sequence[Mapping[str, object]],
    *,
    expected_kind: str,
    repository: str = DEFAULT_REPOSITORY,
    branch: str = DEFAULT_BRANCH,
) -> str:
    actual_kind = str(manifest.get("kind") or "unavailable")
    status = str(manifest.get("status") or "unavailable")
    ready = status == "success" and actual_kind == expected_kind
    review_status = "ready" if ready else "unavailable"
    batch_id = str(manifest.get("batch_id") or "unavailable")
    data_range = manifest.get("data_range") if isinstance(manifest.get("data_range"), Mapping) else {}
    summary = "\n".join((
        f"expected_kind: {expected_kind}",
        f"review_status: {review_status}",
        f"batch_id: {_plain(batch_id)}",
        f"status: {_plain(status)}",
        f"actual_started_at: {_plain(manifest.get('actual_started_at'))}",
        f"completed_at: {_plain(manifest.get('completed_at'))}",
        f"data_range: {_plain(data_range)}",
        f"trigger_type: {_plain(manifest.get('trigger_type'))}",
        f"coverage_mode: {_plain(manifest.get('coverage_mode'))}",
        f"generated_at: {_plain(_generated_at(manifest))}",
        f"source_commit_sha: {_plain(manifest.get('source_commit_sha'))}",
    ))
    body = [
        f"<h1>{expected_kind.title()} Review Input</h1>",
        f'<pre class="machine-summary">{_safe(summary)}</pre>',
        "<section><h2>Batch Status</h2>",
        _definition_table((
            ("batch_id", manifest.get("batch_id")),
            ("status", manifest.get("status")),
            ("kind", manifest.get("kind")),
            ("trigger_type", manifest.get("trigger_type")),
            ("coverage_mode", manifest.get("coverage_mode")),
            ("actual_started_at", manifest.get("actual_started_at")),
            ("completed_at", manifest.get("completed_at")),
            ("generated_at", _generated_at(manifest)),
            ("source_commit_sha", manifest.get("source_commit_sha")),
        )),
        "</section>",
        "<section><h2>Data Range</h2>",
        _definition_table((
            ("start", data_range.get("start")),
            ("end", data_range.get("end")),
            ("lookback_start", data_range.get("lookback_start")),
        )),
        "</section>",
    ]
    if not ready:
        reason = f"status is {status}" if status != "success" else f"kind is {actual_kind}, expected {expected_kind}"
        body.extend((
            '<section class="unavailable"><h2>Review Unavailable</h2>',
            f"<p>{_safe(reason)}. No candidate or historical content is displayed.</p></section>",
            "<section><h2>Original Public JSON Links</h2>",
            _link_list(_raw_links(repository, branch, batch_id, ("manifest.json",))),
            "</section>",
        ))
    else:
        sections = candidates.get("sections") if isinstance(candidates.get("sections"), Mapping) else {}
        for section_key, heading in SECTION_HEADINGS:
            records = sections.get(section_key, []) if isinstance(sections, Mapping) else []
            body.extend((f"<section><h2>{heading}</h2>", _render_records(records), "</section>"))
        body.extend((
            "<section><h2>Duplicate Audit</h2>",
            _render_records(candidates.get("duplicate_audit", [])),
            "</section>",
            "<section><h2>Normalization Audit</h2>",
            _json_block(candidates.get("normalization_audit", {})),
            "</section>",
            "<section><h2>GPT Review Plan</h2>",
            _json_block(candidates.get("gpt_review_plan", {})),
            "</section>",
            "<section><h2>Recent Successful Handoffs</h2>",
            _render_records(recent_events),
            "</section>",
            "<section><h2>Original Public JSON Links</h2>",
            _link_list(_raw_links(
                repository,
                branch,
                batch_id,
                ("manifest.json", f"{expected_kind}-candidates.json", "recent-events.json"),
            )),
            "</section>",
        ))
    return _document(
        f"{expected_kind.title()} Review Input｜Personal Intelligence Briefing",
        f"{expected_kind}批次的公开、只读、服务器渲染审核输入。",
        "\n".join(body),
    )


def _render_records(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        return "<p>No records.</p>"
    rendered = []
    for item in value:
        record = item if isinstance(item, Mapping) else {"core_change": item}
        rows = []
        for field in EVENT_FIELDS:
            field_value = record.get(field)
            if field == "canonical_url":
                rows.append(f"<dt>{field}</dt><dd>{_safe_link(field_value)}</dd>")
            else:
                rows.append(f"<dt>{field}</dt><dd>{_display(field_value)}</dd>")
        rendered.append(f'<article class="event"><dl>{"".join(rows)}</dl></article>')
    return "\n".join(rendered)


def _definition_table(rows: Sequence[tuple[str, object]]) -> str:
    body = "".join(f"<tr><th scope=\"row\">{_safe(key)}</th><td>{_display(value)}</td></tr>" for key, value in rows)
    return f'<div class="table-wrap"><table><tbody>{body}</tbody></table></div>'


def _json_block(value: object) -> str:
    return f'<pre class="json">{_safe(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))}</pre>'


def _raw_links(repository: str, branch: str, batch_id: str, filenames: Sequence[str]) -> list[tuple[str, str]]:
    encoded_batch = quote(batch_id, safe="")
    base = f"https://raw.githubusercontent.com/{repository}/{branch}/delivery/current"
    return [(filename, f"{base}/{filename}?batch={encoded_batch}") for filename in filenames]


def _link_list(links: Sequence[tuple[str, str]]) -> str:
    items = "".join(
        f'<li><a href="{escape(url, quote=True)}" rel="noopener noreferrer external">{_safe(label)}</a></li>'
        for label, url in links
    )
    return f"<ul>{items}</ul>"


def _safe_link(value: object) -> str:
    text = _plain(value)
    parsed = urlsplit(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password:
        href = escape(text, quote=True)
        return f'<a href="{href}" rel="noopener noreferrer external">{_safe(text)}</a>'
    return _safe(text)


def _display(value: object) -> str:
    if value is None or value == "":
        return '<span class="missing">—</span>'
    if isinstance(value, (Mapping, list, tuple)):
        return _safe(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return _safe(value)


def _plain(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _safe(value: object) -> str:
    return escape(_redact(_plain(value)), quote=True)


def _redact(text: str) -> str:
    redacted = text
    for name, value in os.environ.items():
        if SECRET_ENV_NAME.search(name) and len(value) >= 8:
            redacted = redacted.replace(value, "[REDACTED]")
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _generated_at(manifest: Mapping[str, object]) -> object:
    return manifest.get("completed_at") or manifest.get("actual_started_at") or manifest.get("started_at") or "unavailable"


def _document(title: str, description: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{_safe(description)}">
  <meta name="robots" content="index,follow">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <title>{_safe(title)}</title>
  <link rel="stylesheet" href="{SITE_PREFIX}/assets/style.css">
</head>
<body>
  <header class="site-header">
    <a href="{SITE_PREFIX}/">Personal Intelligence Briefing</a>
    <nav aria-label="主导航">
      <a href="{SITE_PREFIX}/current/status/">Status</a>
      <a href="{SITE_PREFIX}/current/morning/">Morning</a>
      <a href="{SITE_PREFIX}/current/noon/">Noon</a>
    </nav>
  </header>
  <main>{body}</main>
  <footer><p>Public read-only view. JSON remains the source of truth.</p></footer>
</body>
</html>
"""


def _stylesheet() -> str:
    return """* { box-sizing: border-box; }
body { margin: 0; color: #18202a; background: #f7f8fa; font: 16px/1.6 system-ui, sans-serif; }
a { color: #0759b8; overflow-wrap: anywhere; }
.site-header, main, footer { max-width: 1120px; margin: 0 auto; padding: 1rem 1.25rem; }
.site-header { display: flex; justify-content: space-between; gap: 1rem; border-bottom: 1px solid #d8dee7; }
.site-header nav { display: flex; gap: 1rem; }
section, article.event { margin: 1rem 0; padding: 1rem; background: #fff; border: 1px solid #d8dee7; border-radius: .5rem; }
h1, h2 { line-height: 1.25; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #eef2f6; padding: 1rem; border-radius: .35rem; }
dl { display: grid; grid-template-columns: minmax(10rem, 14rem) 1fr; gap: .35rem 1rem; }
dt, th { font-weight: 700; text-align: left; }
dd { margin: 0; overflow-wrap: anywhere; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: .45rem; border-bottom: 1px solid #e4e8ee; vertical-align: top; }
.unavailable { border-color: #bf6a00; }
.missing { color: #697386; }
@media (max-width: 680px) { .site-header { display: block; } dl { grid-template-columns: 1fr; } dt { margin-top: .5rem; } }
"""


def _validate_public_outputs(pages: Mapping[str, str]) -> None:
    combined = "\n".join(pages.values())
    checks = {
        "script tag": re.search(r"<\s*script\b", combined, re.IGNORECASE),
        "javascript URL": re.search(r"(?:href|src)\s*=\s*[\"']\s*javascript:", combined, re.IGNORECASE),
        "authorization header": re.search(r"\bAuthorization\b\s*[:=]", combined, re.IGNORECASE),
        "bearer token": re.search(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", combined, re.IGNORECASE),
        "API key pattern": re.search(r"\b(?:sk-|github_pat_|gh[pousr]_)[A-Za-z0-9_-]{8,}", combined, re.IGNORECASE),
    }
    failures = [name for name, match in checks.items() if match]
    if failures:
        raise ValueError(f"unsafe public page output: {', '.join(failures)}")


def _output_paths(output: Path) -> dict[str, Path]:
    return {
        "index": output / "index.html",
        "status": output / "current/status/index.html",
        "morning": output / "current/morning/index.html",
        "noon": output / "current/noon/index.html",
        "style": output / "assets/style.css",
    }


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path, *, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
