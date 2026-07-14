# 仓库目录、命名与归档约定

**状态：** MVP 目标结构。当前仅设计文档存在；应用代码和运行数据需在实施计划获批后创建。

## 1. 目录树

```text
personal-intelligence-briefing/
├── README.md                              # 项目入口与安全边界
├── pyproject.toml                         # Python 工具、测试和格式化配置
├── .gitignore
│
├── .github/
│   └── workflows/
│       ├── test.yml                       # 单元测试和静态检查
│       ├── manual-run.yml                 # workflow_dispatch，仅用于受控测试
│       ├── morning-briefing.yml           # 晨间定时批次
│       └── noon-briefing.yml              # 午间定时批次
│
├── config/                                # 人工评审后才修改的版本化规则
│   ├── sources/
│   │   ├── official-v1.yml                # 一级事实来源
│   │   └── discovery-v1.yml               # 二级候选发现来源
│   ├── policies/
│   │   ├── event-retention-v1.yml         # 热/温/冷去重窗口
│   │   ├── report-selection-v1.yml        # 推送阈值、来源等级和状态映射
│   │   └── model-routing-v1.yml           # MiniMax 默认、Kimi 升级条件
│   └── learning/
│       └── weekly-schedule-v1.yml         # 周内主题、时段与间隔复习规则
│
├── src/intelligence_briefing/             # 可测试的应用代码
│   ├── cli.py                             # 运行入口：morning / noon / manual
│   ├── models.py                          # 事件、批次和来源数据模型
│   ├── time_window.py                     # 北京时间与回查窗口
│   ├── url_normalization.py               # URL 规范化
│   ├── fingerprints.py                    # 内容哈希和事件指纹
│   ├── storage.py                         # JSON/JSONL 读写与月度分区
│   ├── deduplication.py                   # 热/温窗口候选召回与状态判断
│   ├── learning_schedule.py               # 学习槽位选择，不保存个人数据
│   ├── reporting.py                       # JSON/Markdown/manifest 渲染
│   ├── collectors/                        # 官方源与发现源采集器
│   └── llm/                               # MiniMax、Kimi 客户端和结构化校验
│
├── tests/                                 # 与 src 模块一一对应的测试
│   ├── fixtures/                          # 不含密钥和受版权全文的最小夹具
│   ├── test_time_window.py
│   ├── test_url_normalization.py
│   ├── test_fingerprints.py
│   ├── test_storage.py
│   ├── test_deduplication.py
│   ├── test_learning_schedule.py
│   └── test_reporting.py
│
├── data/                                  # GitHub Actions 写入的结构化状态，不存全文
│   ├── events/YYYY/MM/events-YYYY-MM.jsonl
│   ├── runs/YYYY/MM/run-<batch-id>.json
│   ├── watermarks/source-watermarks.json  # 各来源最后成功采集位置
│   └── indexes/active-events.json         # 可重建：只含热/温窗口事件
│
├── delivery/                              # 对 ChatGPT 和人工阅读的交付层
│   ├── current/                           # 固定文件名，成功批次后覆盖
│   │   ├── manifest.json
│   │   ├── morning-candidates.json
│   │   ├── noon-candidates.json
│   │   ├── recent-events.json
│   │   ├── morning-preliminary.md
│   │   └── noon-preliminary.md
│   └── archive/YYYY/MM/DD/<batch-id>/     # 不可变批次快照
│       ├── manifest.json
│       ├── candidates.json
│       └── preliminary.md
│
└── docs/                                  # 静态项目知识，不与运行数据混放
    ├── product/
    │   └── project-brief.md
    ├── architecture/
    │   └── repository-layout.md
    ├── decisions/
    │   └── decision-log.md
    ├── operations/
    │   └── runbook.md
    └── superpowers/
        ├── specs/
        └── plans/
```

`YYYY/MM/DD` 是北京时间自然日；`<batch-id>` 采用 `morning-YYYYMMDDTHHMMSS+0800` 或 `noon-YYYYMMDDTHHMMSS+0800`。文件名不使用“今天”“最新版”一类会随时间失效的自然语言。

## 2. 覆盖、追加与不可变规则

| 位置 | 写入方式 | 原因 |
| --- | --- | --- |
| `config/`、`src/`、`tests/`、`docs/` | 仅通过人工提交或 PR 修改 | 规则和代码必须可审阅、可回滚 |
| `data/events/YYYY/MM/*.jsonl` | 向当月文件追加新状态记录 | 保留事件首次发现和后续状态演化 |
| `data/runs/YYYY/MM/*.json` | 每个批次新建一个文件 | 让失败、重跑和时间边界可追溯 |
| `data/watermarks/`、`data/indexes/` | 覆盖更新，可由历史重建 | 只保存当前运行所需的派生状态 |
| `delivery/archive/` | 仅创建，不修改 | 保留每次候选包的审计快照 |
| `delivery/current/` | 仅在批次完整成功后覆盖 | 为 ChatGPT 提供稳定、短路径的读取入口 |

失败批次不得覆盖 `delivery/current/`。失败详情只写入对应 `data/runs/...` 和该批次的 `delivery/archive/.../manifest.json`，使 ChatGPT 能识别“上游失败”，而不会误读昨天的成功文件。

## 3. 事件保留与比较边界

- **热窗口（默认 14 天）：** 进入严格去重索引；
- **温窗口（默认至 90 天）：** 只作为关联和实质更新的候选；
- **冷归档（90 天后）：** 保留 JSONL 记录，不进入日常自动比较。

窗口数值集中在 `config/policies/event-retention-v1.yml`，并按来源类别配置。每次变更必须同步更新 `docs/decisions/decision-log.md` 的日期、依据、旧值和新值。这样 2026 年 7 月的规则与后续规则可清楚区分。

## 4. ChatGPT 与 Codex 的同步边界

ChatGPT 只读取 `delivery/current/`，并先以 `manifest.json` 的 `git_commit_sha` 和 `archive_path` 锁定本次审核版本。它的文字重排不改写 GitHub 状态。

若 ChatGPT 发现系统性错误，应产生带 `batch_id`、`git_commit_sha`、`event_id`、期望状态和证据链接的结构化缺陷说明，再由 Codex 修复代码、配置和测试。未来自动写回只允许进入独立的 `feedback/chatgpt-review/` 目录，且不属于 MVP。
