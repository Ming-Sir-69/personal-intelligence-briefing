# Personal Intelligence Briefing MVP Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cloud-run, testable first-stage pipeline that converts public AI-source candidates into deduplicated GitHub candidate packets for later ChatGPT review.

**Architecture:** Python code stores append-only event history and immutable batch snapshots in the default branch. Deterministic code owns time, URLs, fingerprints, retention and delivery; MiniMax only normalizes ambiguous content, while Kimi is a capped, optional arbitrator. GitHub Actions produces candidate files; ChatGPT consumes them but does not write state in the MVP.

**Tech Stack:** Python 3.12, standard library dataclasses, PyYAML, httpx, pytest, GitHub Actions.

## Global Constraints

- Use the repository's configured default branch dynamically; never assume `main` or `master` in code or workflow logic.
- All timestamps are timezone-aware `Asia/Shanghai` ISO 8601 values.
- Retention bands are exactly `0–14`, `15–30`, `31–60`, `61–90`, then history-only after 90 days.
- Do not store source full text, API keys, private feedback, company material or copyrighted articles.
- GitHub Actions reads only `MINIMAX_FOR_CODING_API_KEY` and `KIMI_API_KEY` as Secrets; no secret may appear in logs or committed files.
- Kimi is disabled unless all four non-secret Actions Variables are configured: `KIMI_BRIEFING_MONTHLY_TOKEN_LIMIT`, `KIMI_RATE_WINDOW_SECONDS`, `KIMI_MAX_REQUESTS_PER_WINDOW`, `KIMI_MAX_TOKENS_PER_WINDOW`.
- A Kimi request is sequential, ≤6,000 input tokens and ≤1,000 output tokens; at most two calls per batch. `429`, exhausted budget or missing configuration produces `uncertain`, never unbounded retries.
- `delivery/current/` is overwritten only after a complete successful batch; `delivery/archive/YYYY-MM/<batch-id>/` is immutable.
- Do not change existing ChatGPT scheduled tasks in this plan.

---

## Role and Gate Plan

| Gate | Codex | ChatGPT | 铭哥 |
| --- | --- | --- | --- |
| G0：计划确认 | 按本计划在功能分支实施；不改计划任务 | 只检查交付接口，不写 GitHub 状态 | 确认计划执行方式；提供 Kimi 控制台的月度与速率数值 |
| G1：确定性基础 | 完成任务 1—4 与单元测试，不运行云端批次 | 不修改现有晨报/午报 | 无需操作 |
| G2：模型、交付与手动批次 | 完成任务 5—7；以模拟 API 和受控真实调用验证 | 审阅 `manifest`、候选 JSON 和 Markdown 是否满足最终审稿输入 | 在 Actions Variables 写入 Kimi 限额；手动触发一次工作流并审阅候选包 |
| G3：云端验收 | 完成任务 8—9，提交 PR 和运行证据 | 在 GitHub 输出稳定后，单独配置 07:30 / 13:30 的计划任务 | 批准 PR；连续一周标记重复、遗漏或低价值项 |

## Planned Files

```text
pyproject.toml
config/sources-official-v1.yml
config/sources-discovery-v1.yml
config/event-retention-v1.yml
config/report-selection-v1.yml
config/model-routing-v1.yml
config/learning-schedule-v1.yml
src/intelligence_briefing/{__init__,models,time_window,url_normalization,fingerprints,storage,deduplication,llm,reporting,collectors,cli}.py
tests/test_{models,time_window,url_normalization,fingerprints,storage,deduplication,llm,reporting,collectors,cli,workflows}.py
.github/workflows/{test,manual-run,morning-briefing,noon-briefing}.yml
docs/{operations/runbook,decisions/decision-log}.md
```

No `collectors/`, `llm/`, `fixtures/`, database, PDF/Word export, feedback writeback or additional long-lived branch is created in this stage.

### Task 1: Initialize the testable project contract

**Files:**
- Create: `pyproject.toml`
- Create: `src/intelligence_briefing/__init__.py`
- Create: `src/intelligence_briefing/models.py`
- Create: `tests/test_models.py`
- Create: `config/event-retention-v1.yml`
- Create: `config/model-routing-v1.yml`
- Create: `config/report-selection-v1.yml`
- Create: `config/sources-official-v1.yml`
- Create: `config/sources-discovery-v1.yml`
- Create: `config/learning-schedule-v1.yml`

**Interfaces:**
- Produces: immutable `Event`, `SourceItem`, `Batch`, and `ModelUsage` dataclasses with `to_dict()` / `from_dict()` methods.
- Consumes: no application code; later tasks import types only from `models.py`.

- [ ] **Step 1: Write failing model-serialization tests**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from intelligence_briefing.models import Event


def test_event_round_trip_preserves_timezone_and_status() -> None:
    event = Event(
        event_id="evt-openai-codex-20260714",
        status="new_event",
        subject="OpenAI",
        object_name="Codex",
        action="release",
        event_at=datetime(2026, 7, 14, 6, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        canonical_url="https://example.com/release",
        fingerprint="openai|codex|release|2026-07-14|parallel",
    )
    assert Event.from_dict(event.to_dict()) == event
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_models.py::test_event_round_trip_preserves_timezone_and_status -v`
Expected: FAIL because `intelligence_briefing.models` does not exist.

- [ ] **Step 3: Implement the minimal dataclasses and configuration schema**

```python
@dataclass(frozen=True)
class Event:
    event_id: str
    status: str
    subject: str
    object_name: str
    action: str
    event_at: datetime | None
    canonical_url: str
    fingerprint: str
    # to_dict serializes datetime with isoformat; from_dict uses datetime.fromisoformat.


@dataclass(frozen=True)
class Batch:
    batch_id: str
    kind: Literal["morning", "noon"]
    status: Literal["success", "partial", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
```

Put the four retention bands and the 90-day history boundary in `event-retention-v1.yml`. Put the four Kimi Action Variable names, per-call caps, two-call batch cap, and MiniMax-first route in `model-routing-v1.yml`.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_models.py -v`
Expected: PASS.

Run: `pytest -q`
Expected: PASS with one test.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml config src/intelligence_briefing tests/test_models.py
git commit -m "feat: add briefing data contract"
```

### Task 2: Implement time bands, URLs and stable fingerprints

**Files:**
- Create: `src/intelligence_briefing/time_window.py`
- Create: `src/intelligence_briefing/url_normalization.py`
- Create: `src/intelligence_briefing/fingerprints.py`
- Create: `tests/test_time_window.py`
- Create: `tests/test_url_normalization.py`
- Create: `tests/test_fingerprints.py`

**Interfaces:**
- Produces: `age_band(event_at, now) -> Literal["hot", "warm", "cold", "archive", "history"]`, `normalize_url(url) -> str`, `event_fingerprint(...) -> str`.
- Consumes: `Event` from `models.py`.

- [ ] **Step 1: Write failing boundary and normalization tests**

```python
def test_age_band_has_no_overlap_at_30_days() -> None:
    now = datetime(2026, 7, 31, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert age_band(now - timedelta(days=30), now) == "warm"
    assert age_band(now - timedelta(days=31), now) == "cold"


def test_normalize_url_removes_tracking_and_fragment() -> None:
    assert normalize_url("https://a.example/x?utm_source=x&id=1#top") == "https://a.example/x?id=1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_time_window.py tests/test_url_normalization.py tests/test_fingerprints.py -v`
Expected: FAIL because the modules are absent.

- [ ] **Step 3: Implement only deterministic behavior**

```python
def age_band(event_at: datetime | None, now: datetime) -> str:
    if event_at is None:
        return "hot"
    age = max(0, (now.date() - event_at.astimezone(SHANGHAI).date()).days)
    if age <= 14: return "hot"
    if age <= 30: return "warm"
    if age <= 60: return "cold"
    if age <= 90: return "archive"
    return "history"
```

Build the fingerprint from normalized lowercase subject, object, action, official event date and normalized core change; hash it with SHA-256 so it is stable but compact.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_time_window.py tests/test_url_normalization.py tests/test_fingerprints.py -v`
Expected: PASS.

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/intelligence_briefing tests/test_time_window.py tests/test_url_normalization.py tests/test_fingerprints.py
git commit -m "feat: add deterministic event identity rules"
```

### Task 3: Add append-only state and short-horizon event recall

**Files:**
- Create: `src/intelligence_briefing/storage.py`
- Create: `src/intelligence_briefing/deduplication.py`
- Create: `tests/test_storage.py`
- Create: `tests/test_deduplication.py`

**Interfaces:**
- Consumes: `Event`, `age_band`, normalized URL and fingerprint.
- Produces: `append_event(root, event)`, `load_recall_candidates(root, event, now)`, `classify_deterministic(candidate, history) -> str`.

- [ ] **Step 1: Write failing tests for monthly append and 90-day cutoff**

```python
def test_history_older_than_90_days_is_not_returned_without_exact_id(tmp_path) -> None:
    now = datetime(2026, 7, 14, tzinfo=ZoneInfo("Asia/Shanghai"))
    append_event(tmp_path, make_event("old", now=now, days_ago=91))
    append_event(tmp_path, make_event("fresh", now=now, days_ago=10))
    recalled = load_recall_candidates(tmp_path, make_event("candidate", now=now, days_ago=0), now=now)
    assert [event.event_id for event in recalled] == ["fresh"]


def make_event(name: str, now: datetime, days_ago: int) -> Event:
    return Event(
        event_id=name,
        status="new_event",
        subject="OpenAI",
        object_name=name,
        action="release",
        event_at=now - timedelta(days=days_ago),
        canonical_url=f"https://example.com/{name}",
        fingerprint=name,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage.py tests/test_deduplication.py -v`
Expected: FAIL because storage and recall functions are absent.

- [ ] **Step 3: Implement append-only JSONL and exact first-pass deduplication**

```python
def event_file(root: Path, observed_at: datetime) -> Path:
    return root / "data" / "events" / f"events-{observed_at:%Y-%m}.jsonl"

def classify_deterministic(candidate: Event, history: Sequence[Event]) -> str:
    if any(item.canonical_url == candidate.canonical_url for item in history):
        return "duplicate"
    if any(item.fingerprint == candidate.fingerprint for item in history):
        return "duplicate"
    return "needs_semantic_review"
```

The recall function may include hot events for semantic comparison, warm events only for same structural identifiers, cold/archive events only for exact keys, and history events only for permanent exact identifiers.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_storage.py tests/test_deduplication.py -v`
Expected: PASS.

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/intelligence_briefing tests/test_storage.py tests/test_deduplication.py
git commit -m "feat: add bounded event state recall"
```

### Task 4: Implement capped model routing and safe fallbacks

**Files:**
- Create: `src/intelligence_briefing/llm.py`
- Create: `tests/test_llm.py`

**Interfaces:**
- Produces: `ModelRouter.route(candidate, history) -> ArbitrationResult`.
- Consumes: normalized candidate, recalled events and API usage returned by provider clients.

- [ ] **Step 1: Write failing routing tests**

```python
EVENT = Event(
    event_id="evt-1", status="new_event", subject="OpenAI", object_name="Codex",
    action="release", event_at=None, canonical_url="https://example.com/1", fingerprint="evt-1",
)


class FakeKimi:
    def __init__(self) -> None:
        self.calls = 0

    def arbitrate(self, payload: dict[str, object]) -> ArbitrationResult:
        self.calls += 1
        return ArbitrationResult(status="new_event", reason="fake")


class FakeMiniMax:
    def extract(self, candidate: Event, history: list[Event]) -> ArbitrationResult:
        return ArbitrationResult(status="new_event", reason="clear")


class LowConfidenceMiniMax(FakeMiniMax):
    def extract(self, candidate: Event, history: list[Event]) -> ArbitrationResult:
        return ArbitrationResult(status="uncertain", reason="low_confidence", needs_kimi=True)


def test_kimi_is_not_called_without_all_budget_variables(monkeypatch) -> None:
    router = ModelRouter(minimax=FakeMiniMax(), kimi=FakeKimi(), settings=missing_kimi_limits())
    result = router.route(candidate=EVENT, history=[])
    assert result.status == "uncertain"
    assert router.kimi.calls == 0


def test_kimi_stops_after_two_calls_in_one_batch() -> None:
    router = ModelRouter(minimax=LowConfidenceMiniMax(), kimi=FakeKimi(), settings=valid_limits())
    [router.route(candidate=EVENT, history=[]) for _ in range(3)]
    assert router.kimi.calls == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL because `ModelRouter` is absent.

- [ ] **Step 3: Implement provider-neutral routing**

```python
class ModelRouter:
    def route(self, candidate: Event, history: list[Event]) -> ArbitrationResult:
        normalized = self.minimax.extract(candidate, history[:3])
        if not normalized.needs_kimi:
            return normalized
        if not self.budget.can_call_kimi(max_input=6000, max_output=1000):
            return ArbitrationResult(status="uncertain", reason="kimi_budget_unavailable")
        return self.kimi.arbitrate(normalized.compact_payload())
```

The Kimi client must make one request at a time, inspect provider usage, stop on `429`, and never log authorization headers or request bodies containing credentials. MiniMax remains the default route.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_llm.py -v`
Expected: PASS.

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/intelligence_briefing/llm.py tests/test_llm.py config/model-routing-v1.yml
git commit -m "feat: add budgeted model arbitration"
```

### Task 5: Render immutable candidate packets and stable current pointers

**Files:**
- Create: `src/intelligence_briefing/reporting.py`
- Create: `tests/test_reporting.py`

**Interfaces:**
- Produces: `write_batch(root, batch, events) -> Path`.
- Consumes: classified events and `ModelUsage` records.
- Guarantees: `delivery/current/` changes only after all archive files and `manifest.json` are complete.

- [ ] **Step 1: Write failing delivery tests**

```python
def test_successful_batch_writes_archive_then_current_pointer(tmp_path) -> None:
    current_batch = Batch(
        batch_id="morning-20260714T062000+0800",
        kind="morning",
        status="success",
        started_at=datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    write_batch(tmp_path, current_batch, [EVENT])
    assert (tmp_path / "delivery/archive/2026-07/morning-20260714T062000+0800/manifest.json").exists()
    current = json.loads((tmp_path / "delivery/current/manifest.json").read_text())
    assert current["archive_path"].endswith("morning-20260714T062000+0800")


def test_failed_batch_does_not_replace_current(tmp_path) -> None:
    successful = Batch(
        batch_id="morning-20260714T062000+0800",
        kind="morning",
        status="success",
        started_at=datetime(2026, 7, 14, 6, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    failed = Batch(
        batch_id="noon-20260714T122000+0800",
        kind="noon",
        status="failed",
        started_at=datetime(2026, 7, 14, 12, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    write_batch(tmp_path, successful, [EVENT])
    write_failed_batch(tmp_path, failed, "collector timeout")
    assert read_current_batch_id(tmp_path) == successful.batch_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reporting.py -v`
Expected: FAIL because the reporting module is absent.

- [ ] **Step 3: Implement the seven candidate sections and manifest**

```python
def write_batch(root: Path, batch: Batch, events: list[Event]) -> Path:
    archive = root / "delivery" / "archive" / batch.started_at.strftime("%Y-%m") / batch.batch_id
    archive.mkdir(parents=True, exist_ok=False)
    payload = build_candidate_payload(batch, events)
    write_json(archive / "candidates.json", payload)
    write_text(archive / "preliminary.md", render_preliminary(payload))
    write_json(archive / "manifest.json", build_manifest(batch, archive, payload))
    if batch.status == "success":
        replace_current_from_archive(root, archive, batch.kind)
    return archive
```

The preliminary Markdown and JSON must contain exactly: batch state/range, high-priority candidates, other valid candidates, Agentic Coding/tool-chain candidates, product/industry/policy candidates, uncertain/late candidates, and quality metrics. `manifest.json` includes batch ID, status, time range, archive path, commit SHA placeholder filled by workflow, counts, error list and model usage.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_reporting.py -v`
Expected: PASS.

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/intelligence_briefing/reporting.py tests/test_reporting.py
git commit -m "feat: add versioned candidate delivery"
```

### Task 6: Add limited source collection and a manual CLI path

**Files:**
- Create: `src/intelligence_briefing/collectors.py`
- Create: `src/intelligence_briefing/cli.py`
- Create: `tests/test_collectors.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces: `collect_sources(config) -> list[SourceItem]`, `python -m intelligence_briefing.cli --batch morning --dry-run`.
- Consumes: official/discovery YAML source lists; only source URLs and metadata.

- [ ] **Step 1: Write failing tests with local HTTP transport mocks**

```python
def test_collector_returns_metadata_without_storing_full_article() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200,
        text="<rss><channel><item><link>https://example.com/release</link></item></channel></rss>",
    ))
    item = collect_sources(source_config(), client=httpx.Client(transport=transport))[0]
    assert item.url == "https://example.com/release"
    assert not hasattr(item, "full_article")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_collectors.py tests/test_cli.py -v`
Expected: FAIL because collector and CLI are absent.

- [ ] **Step 3: Implement the minimum initial source set**

Implement RSS/Atom and JSON endpoint collection only for the MVP's official OpenAI, Anthropic, Claude Code, Codex, DeepSeek, MiniMax, Kimi, GitHub Trending and Hugging Face Daily Papers configurations. Discovery sources only create candidates; they never become the final factual source without a configured official URL.

- [ ] **Step 4: Run focused and full tests**

Run: `pytest tests/test_collectors.py tests/test_cli.py -v`
Expected: PASS.

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/intelligence_briefing tests/test_collectors.py tests/test_cli.py config/sources-*.yml
git commit -m "feat: add controlled source collection"
```

### Task 7: Add cloud workflows and prove the manual batch

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/manual-run.yml`
- Create: `.github/workflows/morning-briefing.yml`
- Create: `.github/workflows/noon-briefing.yml`
- Modify: `README.md`
- Modify: `docs/operations/runbook.md`

**Interfaces:**
- Produces: manual `workflow_dispatch` with `morning|noon` and `dry_run` inputs; scheduled runs at 06:20 and 12:20 China time expressed correctly in UTC cron.
- Consumes: repository Secrets and optional Kimi Actions Variables.

- [ ] **Step 1: Write workflow assertions as repository-level checks**

```python
def test_scheduled_workflows_have_write_lock_and_distinct_cron() -> None:
    morning = yaml.load(Path(".github/workflows/morning-briefing.yml").read_text(), Loader=yaml.BaseLoader)
    noon = yaml.load(Path(".github/workflows/noon-briefing.yml").read_text(), Loader=yaml.BaseLoader)
    assert morning["permissions"]["contents"] == "write"
    assert morning["concurrency"]["cancel-in-progress"] == "false"
    assert morning["on"]["schedule"][0]["cron"] != noon["on"]["schedule"][0]["cron"]
```

Use cron `20 22 * * *` for the 06:20 Beijing morning run and `20 4 * * *` for the 12:20 Beijing noon run. Also assert that each workflow text contains neither `echo ${{ secrets.` nor a hardcoded `refs/heads/main` / `refs/heads/master`.

- [ ] **Step 2: Run workflow assertions to verify they fail**

Run: `pytest tests/test_workflows.py -v`
Expected: FAIL because workflow files do not exist.

- [ ] **Step 3: Implement workflows with one write authority**

```yaml
permissions:
  contents: write
concurrency:
  group: briefing-${{ inputs.batch || 'scheduled' }}
  cancel-in-progress: false
```

The action must run tests before a non-dry-run write, execute the CLI, commit only changed generated state, and use the GitHub-configured default branch rather than a hardcoded branch name. The scheduled workflow must not overwrite `delivery/current/` when the batch is partial or failed.

- [ ] **Step 4: Run tests and manually dispatch a dry run**

Run: `pytest -q`
Expected: PASS.

Run in GitHub: `manual-run.yml` with `batch=morning`, `dry_run=true`.
Expected: a successful run that logs no secret and creates no repository commit.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows README.md docs/operations/runbook.md tests/test_workflows.py
git commit -m "ci: add briefing workflow controls"
```

### Task 8: Perform the first controlled live batch and hand off to ChatGPT

**Files:**
- Modify: `docs/operations/runbook.md`
- Modify: `docs/decisions/decision-log.md`
- Generated: `data/`, `delivery/current/`, `delivery/archive/YYYY-MM/<batch-id>/`

**Interfaces:**
- Produces: one verifiable successful candidate packet and a documented readiness decision for ChatGPT.
- Consumes: a user-triggered production-mode manual workflow and the user-configured API limits.

- [ ] **Step 1: Add a readiness checklist before running live**

The checklist requires: Secrets exist, Kimi Variables are either complete or Kimi is intentionally disabled, manual dry run succeeded, at least one duplicate fixture passed, and the default branch remains `master`.

- [ ] **Step 2: Run the first live manual batch**

Run in GitHub: `manual-run.yml` with `batch=morning`, `dry_run=false`.
Expected: one archive packet, a current manifest pointing to it, a JSONL event append or explicit no-change state, and no leaked credential.

- [ ] **Step 3: Verify against the delivery contract**

Check the six fixed inputs:

```text
delivery/current/manifest.json
delivery/current/morning-candidates.json
delivery/current/noon-candidates.json
delivery/current/recent-events.json
delivery/current/morning-preliminary.md
delivery/current/noon-preliminary.md
```

The morning run must populate only its relevant candidate/preliminary fields and record absent noon output explicitly; it must not present stale noon data as current.

- [ ] **Step 4: Record the gate outcome and commit only operational documentation**

```bash
git add docs/operations/runbook.md docs/decisions/decision-log.md
git commit -m "docs: record first briefing validation"
```

### Task 9: ChatGPT scheduling gate and one-week quality loop

**Files:**
- Modify: `docs/operations/runbook.md`
- Future external change: existing ChatGPT scheduled tasks, only after the gate passes.

**Interfaces:**
- Produces: an explicit decision whether ChatGPT may consume the GitHub fixed inputs.
- Consumes: at least one successful morning batch, one successful noon batch, one failed-batch simulation and one duplicate regression test.

- [ ] **Step 1: Verify the eight scheduling prerequisites**

Confirm all of the following: manual Actions success; stable manifest; both candidate files generated; `recent-events.json` present; public raw links accessible; duplicate test passed; failed-batch test passed; no API secret appears in files or logs.

- [ ] **Step 2: Hand off the exact scope to ChatGPT**

ChatGPT reads only the fixed `delivery/current/` inputs, checks manifest freshness and status first, then does targeted official-source gap checking. It may delete, reorder and explain candidates but must not write GitHub state, fill with old news, or treat commentary as a fact.

- [ ] **Step 3: Run the seven-day feedback loop**

铭哥 marks each final item as `useful`, `duplicate`, `late`, `missed`, or `low_value`. Codex aggregates only these labels and batch metrics; ChatGPT adjusts task wording only after a documented decision. No automatic feedback writeback is added in this stage.

- [ ] **Step 4: Commit the documented gate result**

```bash
git add docs/operations/runbook.md docs/decisions/decision-log.md
git commit -m "docs: define ChatGPT briefing handoff"
```

## Plan Self-Review

- Spec coverage: deterministic identity, four shortened time bands, 90-day cutoff, Kimi context/rate/month budgets, immutable/current delivery, cloud scheduling, ChatGPT read-only boundary and role gates are covered by Tasks 1—9.
- Placeholder scan: no deferred implementation markers are used; user-owned Kimi limit values are explicitly designated as Actions Variables rather than guessed constants.
- Type consistency: `Event`, `ModelUsage`, `ArbitrationResult`, `ModelRouter`, `write_batch`, and all test targets are introduced before later tasks consume them.
