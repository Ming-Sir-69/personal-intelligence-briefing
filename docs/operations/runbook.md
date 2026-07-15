# 阶段交接与项目记忆

## 当前状态

- 当前阶段：G4 内容溯源修复已通过真实批次验证；确定性标准化守门和 ChatGPT 有界二次研究计划已完成本地接入与无密钥 dry-run。合并后再跑一个真实批次，随后配置正式定时任务。
- 最近验收：ChatGPT G2 复核结论为“允许进入 G3”。
- 已关闭的 G3 前置问题：四档召回、未知事件时间、批次状态、跨批次 `recent-events.json`。
- G3 已实现：测试、手动运行、晨间/午间工作流；成功批次水位线；按来源隔离的采集错误；离线失败/部分失败模拟。
- 已完成本地真实验证（2026-07-15）：MiniMax Token Plan Key 可列出模型；晨间批次处理 10 条窗口内候选并成功；午间批次处理 2 条窗口内候选并成功；失败模拟未覆盖成功的 `delivery/current/`。MiniMax 抽取实际使用 `thinking.disabled`，以避免推理输出挤占结构化 JSON 的预算。
- 已确认的外部边界：当前 `KIMI_API_KEY` 是 Kimi For Coding 会员 Key，不能调用 Moonshot 开放平台 `https://api.moonshot.cn/v1`；它应使用 Kimi Code 的 OpenAI 兼容端点 `https://api.kimi.com/coding/v1` 和模型 `kimi-for-coding`。该模型只接受 `temperature: 1`，因此路由配置显式覆盖共享客户端默认值。2026-07-15 的本地条件仲裁已成功；Kimi 在 MVP 中仍只处理高优先级歧义项。
- 已完成 G3 云端验证：GitHub Secrets 成功注入且日志以 `***` 掩码显示；晨/午 live 批次均生成 `success` 交付；失败模拟仅新增 failed archive，未覆盖 `delivery/current/`；三个固定公开 Raw 入口均返回 HTTP 200。

## 每阶段交接规则

### Codex

在阶段汇报前完成权限范围内的全部工作：实现、测试、离线验证、文档同步、提交和推送。汇报必须给出分支、提交 SHA、PR、变更文件、测试/Actions 证据、已知问题和下一阶段门槛。

### ChatGPT

仅在输入文件已公开可读且阶段门槛满足后执行审核。Codex 必须提供可直接粘贴的任务提示词，说明固定输入、只读边界、验收项和预期输出。ChatGPT 的系统性发现应包含批次、提交、事件、期望状态和证据，供 Codex 修复。

### 铭哥

仅处理无法由 Agent 安全完成的事项：GitHub/Secrets 外部授权、手动触发或界面验证、产品取舍与阅读验收。每次需要阅读时，Codex 必须给出明确文件链接与阅读目的。

## G3 的阅读产物与入口

首次成功晨间/午间批次后：

- 候选初稿：`delivery/current/morning-preliminary.md`、`delivery/current/noon-preliminary.md`；
- 批次新鲜度：`delivery/current/manifest.json`；
- 审计与来源核对：`delivery/current/morning-candidates.json`、`delivery/current/noon-candidates.json`、`delivery/current/recent-events.json`；
- 历史追溯：`delivery/archive/YYYY-MM/<batch-id>/`。

候选初稿服务于上游审计和 GPT 交接；最终面向铭哥阅读的自然语言简报由 G4 ChatGPT 任务输出。

## G3 Actions 操作顺序

1. PR 分支先由 `Tests` 的 `push` 和 `pull_request` 触发自动测试；它不读取 Secrets，也不写入仓库状态；
2. GitHub 将 `workflow_dispatch` 入口注册在默认分支后，运行 `Manual briefing batch` 的 `dry-run`，它使用临时目录、不会读取 API Key 或写入仓库；
3. 依次运行 `morning`、`noon` 的 `live`，只有两者完整成功才更新对应 `delivery/current/` 文件；
4. 运行 `simulate-failed`，确认失败归档存在且 `delivery/current/manifest.json` 保持上一成功批次；
5. 由 Codex 记录工作流 URL、运行 ID、提交 SHA 和公开 Raw 入口；ChatGPT 只在这四项齐备后开始 G4 审核。

`workflow_dispatch` 的 GitHub 手动触发入口需要工作流文件已存在于默认分支。因此当前 PR 合并前只做无密钥 CI 验证；合并后才执行真实批次和失败模拟。`Morning briefing batch` 和 `Noon briefing batch` 的定时表达式分别是 06:20 与 12:20（北京时间），且 GitHub 的计划工作流也只从默认分支触发。

## 2026-07-15 本地真实验证记录

- 公开 feed 采集总计 1,055 条历史条目；经 `lookback_start` 窗口筛选和每源最多 20 条保护后，晨间实际交给 MiniMax 的候选为 10 条，午间为 2 条。
- MiniMax `MiniMax-M3` 的结构化抽取使用 `thinking: {type: disabled}`、`max_tokens: 512`、`reasoning_split: true` 与 45 秒请求超时。真实单条验证返回完整 JSON；晨间和午间集成批次均成功，且失败模拟未覆盖 `delivery/current/`。
- Kimi For Coding 会员 Key 对 Moonshot 开放平台 API 返回 HTTP 401，符合两种 Key 的隔离边界。改用 `https://api.kimi.com/coding/v1`、`kimi-for-coding`、`temperature: 1` 和 `max_tokens: 512` 后，真实条件仲裁成功，返回 `new_event`，实际使用 291 输入 / 335 输出 token。云端工作流应沿用 Coding 路由，不得误用 Moonshot 开放平台入口。
- 2026-07-15 的云端晨间 live、午间 live 与失败模拟均完成模型/状态运行步骤，但首次生成的 `data/`、`delivery/` 文件是 Git 未跟踪文件；三个工作流错误地使用 `git diff --quiet`，导致提交步骤无差异退出。修复已改为 `git status --porcelain -- data delivery` 并有回归测试；修复合并后必须重新运行三项云端验证，确认公开交付文件与失败保护实际落库。

## 2026-07-15 G3 云端复验记录

- 状态提交修复后的首次晨间 live（[run 29409347256](https://github.com/Ming-Sir-69/personal-intelligence-briefing/actions/runs/29409347256)）在提交 `263439c` 上成功：archive 为 `morning-20260715T184740+0800`，10 条候选均归并为历史重复，`delivery/current/` 与 `data/gpt-handoffs/` 已真实提交。
- 午间 live（[run 29409491238](https://github.com/Ming-Sir-69/personal-intelligence-briefing/actions/runs/29409491238)）成功：archive 为 `noon-20260715T185016+0800`，生成 2 条新事件，并更新了 `delivery/current/noon-*`、`recent-events.json` 和 GPT handoff。
- 失败保护模拟（[run 29409590705](https://github.com/Ming-Sir-69/personal-intelligence-briefing/actions/runs/29409590705)）成功完成：archive `morning-20260715T185147+0800` 状态为 `failed`，错误为预期的模拟提供方失败；模拟前后的 `delivery/current/manifest.json` 字节级一致，仍指向午间成功批次。
- 公共 Raw 入口已验证为 HTTP 200：`delivery/current/manifest.json`、`morning-preliminary.md`、`noon-preliminary.md`。本次运行日志中的 Actions Secret 均以 GitHub 掩码显示，代码与产物中未记录 API Key。
- 复验期间发现并合并两项最小恢复修复：`1922a3c` 对缺字段 MiniMax JSON 仅重试一次并累计实际 token；`263439c` 将网络超时转换为可隔离的单来源运行错误。两项均有回归测试，且不放宽 `partial` / `failed` 不覆盖 current 的规则。

## G4 调研边界

GitHub Actions/MiniMax 保留固定高可信来源采集、状态维护和去重责任；ChatGPT 追加高价值定向研究、官方核验与少量 `GPT 定向补录`。它不应无边界地重做全网抓取，否则会绕开 GitHub 的历史状态并重新引入重复。

候选 JSON 根层的 `gpt_review_plan` 是 G4 的机器可读执行合同：先检查 manifest 和批次范围，再读取候选、`normalization_audit` 与 `recent-events.json`；逐条核验候选证据后，按 `priority_source_checks` 做官方源查漏。搜索从候选向相邻的一手发布说明、文档、安全公告、论文或监管原文最多扩展一层；晨间最多补录三条，午间最多补录两条。最终结果必须区分保留、修正、删除、补录和系统缺陷，且不得把 ChatGPT 的任务记忆当成正式去重状态。

标准化守门失败或发生程序修正时，事件的 `normalization_flags` 和根层 `normalization_audit` 会保留原因。ChatGPT 应优先复核这些事件；`normalization_failed` 事件若无法从官方来源恢复，必须删除或保留在不确定区，不得为了报告完整性强行确认。

## 2026-07-15 G4 首轮审核发现与修复范围

G4 通过公开 Raw 入口确认：手动迟到午间批次可产生零长度正式窗口，且失败或部分成功批次写入的观察事件可能参与下一批次的重复抑制。这两项会影响用户是否第一次看到事件，不属于可延后的文档优化。

对应的最小修复必须满足：

- 去重召回只依据此前已进入成功 GitHub 候选包的 handoff；`data/events/` 继续保留所有观察记录，仅用于诊断；
- manifest 明确输出触发来源、计划时间、实际开始时间、回补状态、覆盖模式和零长度窗口标记；
- 候选 JSON 在根层输出 `duplicate_audit`，保留被压制事件的最小公共审计字段；`counts` 仍只包含数值指标；
- 不新增数据库、前端或自动写回通道。修复合并后，由 ChatGPT 对新批次再做一次只读复核。

## 2026-07-16 G4 真实批次内容正确性修复

批次 `morning-20260716T015038+0800` 验证了新的触发、回补和时间窗口语义。G4 保留 GPT-Red，修正 OpenAI 美国 AI 安全文章的事实类型，并删除无明确用户影响的 Codex alpha 构建。

当前阻塞修复仅包括：

- 事件输出增加 `fact_type`，企业政策主张使用发布企业作为主体；
- 事件输出增加 `event_time_precision` 与 `event_time_source`，RSS/Atom 精确时间只表达 feed 发布时间；
- 旧事件记录缺少新字段时保持兼容读取；
- Key 继续只从进程环境读取，错误信息不得包含响应正文、Authorization 或环境值。

连续预发布版本流降噪和 AI HOT 二级线索源接入均登记为后续优化，不阻塞当前 MVP 完整闭环。AI HOT 接入前先用匿名只读接口做小样本覆盖率、重复率和署名合同验证，不安装 MCP，也不新增 Secret。
