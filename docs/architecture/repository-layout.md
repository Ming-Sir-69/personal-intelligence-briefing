# 仓库目录、命名与归档约定

**状态：** G1/G2 基础实现已存在；G3 将首次创建工作流与真实运行数据。目录树同时说明已实现部分和后续阶段的预留边界。

## 1. 目录树

```text
personal-intelligence-briefing/
├── README.md                              # 项目入口与安全边界
├── pyproject.toml                         # Python 工具、测试和格式化配置
├── .gitignore
│
├── .github/
│   └── workflows/
│       ├── tests.yml                      # 单元测试和静态检查
│       ├── manual-run.yml                 # workflow_dispatch，仅用于受控测试
│       ├── morning-briefing.yml           # 晨间定时批次
│       └── noon-briefing.yml              # 午间定时批次
│
├── config/                                # 人工评审后才修改的版本化规则
│   ├── sources-official-v1.yml            # 一级事实来源
│   ├── sources-discovery-v1.yml           # 二级候选发现来源
│   ├── event-retention-v1.yml             # 四段去重窗口
│   ├── report-selection-v1.yml            # 推送阈值、来源等级和状态映射
│   ├── model-routing-v1.yml               # MiniMax 默认、Kimi 预算与升级条件
│   └── learning-schedule-v1.yml           # 独立学习任务、时段与间隔复习规则
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
│   ├── collectors.py                      # 官方源与发现源采集器
│   ├── llm.py                             # MiniMax、Kimi 客户端和结构化校验
│   └── runtime.py                         # GitHub Actions 的真实来源与模型装配
│
├── tests/                                 # 与 src 模块一一对应的测试
│   ├── test_models.py
│   ├── test_time_window.py
│   ├── test_url_normalization.py
│   ├── test_fingerprints.py
│   ├── test_storage.py
│   ├── test_deduplication.py
│   ├── test_learning_schedule.py
│   ├── test_llm.py
│   ├── test_reporting.py
│   ├── test_collectors.py
│   ├── test_cli.py
│   └── test_workflows.py
│
├── data/                                  # GitHub Actions 写入的结构化状态，不存全文
│   ├── events/events-YYYY-MM.jsonl         # 按月追加的事件历史
│   ├── runs/run-<batch-id>.json            # 每个批次一个运行与用量记录
│   ├── source-watermarks.json              # 最后完整成功批次的连续采集边界
│   ├── active-events.json                  # 可重建：只含 0—30 天事件
│   ├── permanent-identifiers.json          # 永久精确键，不参与宽泛语义比对
│   └── gpt-handoffs/                       # 成功候选包进入 GPT 审核入口的追加记录
│       └── handoffs-YYYY-MM.jsonl
│
├── delivery/                              # 对 ChatGPT 和人工阅读的交付层
│   ├── current/                           # 固定文件名，成功批次后覆盖
│   │   ├── manifest.json
│   │   ├── morning-candidates.json
│   │   ├── noon-candidates.json
│   │   ├── recent-events.json
│   │   ├── morning-preliminary.md
│   │   ├── noon-preliminary.md
│   │   └── learning/                       # 独立学习任务的机器可读卡片
│   │       ├── next-audio.json
│   │       ├── reflection-prompt.json
│   │       └── weekly-review.json
│   └── archive/YYYY-MM/<batch-id>/         # 不可变批次快照；批次名含完整日期
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

`YYYY-MM` 是北京时间归档月份；`<batch-id>` 采用 `morning-YYYYMMDDTHHMMSS+0800` 或 `noon-YYYYMMDDTHHMMSS+0800`，因此不需要再嵌套日目录。文件名不使用“今天”“最新版”一类会随时间失效的自然语言。

## 2. 覆盖、追加与不可变规则

| 位置 | 写入方式 | 原因 |
| --- | --- | --- |
| `config/`、`src/`、`tests/`、`docs/` | 仅通过人工提交或 PR 修改 | 规则和代码必须可审阅、可回滚 |
| `data/events/events-YYYY-MM.jsonl` | 向当月文件追加新状态记录 | 保留事件首次发现和后续状态演化 |
| `data/runs/run-<batch-id>.json` | 每个批次新建一个文件，并记录 MiniMax/Kimi 的输入、输出和限额状态 | 让失败、重跑、时间边界与模型用量可追溯 |
| `data/source-watermarks.json`、`data/active-events.json` | 覆盖更新，可由历史重建 | 前者仅在完整成功批次后推进，用于下一批连续边界；后者是当前活动索引 |
| `data/permanent-identifiers.json` | 追加或受控合并 | 保存跨归档期仍可精确查询的 ID，不参与宽泛语义比较 |
| `data/gpt-handoffs/handoffs-YYYY-MM.jsonl` | 仅在成功候选包生成后追加 | 为下一批和 GPT 提供最近 30 天已提交审核的跨批次历史 |
| `delivery/archive/` | 仅创建，不修改 | 保留每次候选包的审计快照 |
| `delivery/current/` | 仅在批次完整成功后覆盖 | 为 ChatGPT 提供稳定、短路径的读取入口 |

失败批次不得覆盖 `delivery/current/`。失败详情只写入对应 `data/runs/...` 和该批次的 `delivery/archive/.../manifest.json`，使 ChatGPT 能识别“上游失败”，而不会误读昨天的成功文件。

## 3. 事件保留与比较边界

- **热窗口（默认 0—14 天）：** 进入严格 URL、哈希、实体和语义去重；
- **温窗口（默认 15—30 天）：** 只按事件链和结构化实体关联，不做宽泛历史语义搜索；
- **冷窗口（默认 31—60 天）：** 只按精确 ID、规范化 URL 和重大例外查询；
- **归档缓冲期（默认 61—90 天）：** 不进入模型召回，只保留永久精确键和重大例外查询；
- **历史期（超过 90 天）：** 不进入日常召回，但永久精确键仍可查询。

窗口数值集中在 `config/event-retention-v1.yml`，并按来源类别配置。每次变更必须同步更新 `docs/decisions/decision-log.md` 的日期、依据、旧值和新值。这样 2026 年 7 月的规则与后续规则可清楚区分。

## 4. ChatGPT 与 Codex 的同步边界

ChatGPT 的 AI 晨报和午报只读取 `delivery/current/`，先检查 `manifest.json` 的 `source_commit_sha`、`workflow_run_id` 和 `archive_path`。实际包含 manifest 的输出提交由 GitHub 文件提交元数据确定，不能在 manifest 内自指为 `output_commit_sha`。`recent-events.json` 是最近 30 天已进入成功 GitHub 候选包的跨批次历史，不是当前候选的复制。独立学习任务只读取 `delivery/current/learning/` 的对应卡片；其一键直达链接必须指向原始单集或原始页面。ChatGPT 的文字重排不改写 GitHub 状态。

默认分支不假定为 `main`：工作流、运行说明和人工脚本必须从仓库元数据或 `origin/HEAD` 读取当前默认分支。当前仓库默认分支为 `master`；它是唯一长期默认分支，功能分支在合并后删除。

若 ChatGPT 发现系统性错误，应产生带 `batch_id`、`source_commit_sha`、`workflow_run_id`、`event_id`、期望状态和证据链接的结构化缺陷说明，再由 Codex 修复代码、配置和测试。未来自动写回只允许进入独立的 `feedback/chatgpt-review/` 目录，且不属于 MVP。
