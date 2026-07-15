# 阶段交接与项目记忆

## 当前状态

- 当前阶段：G3 本地真实运行已通过，待 GitHub Actions 云端验证。
- 最近验收：ChatGPT G2 复核结论为“允许进入 G3”。
- 已关闭的 G3 前置问题：四档召回、未知事件时间、批次状态、跨批次 `recent-events.json`。
- G3 已实现：测试、手动运行、晨间/午间工作流；成功批次水位线；按来源隔离的采集错误；离线失败/部分失败模拟。
- 已完成本地真实验证（2026-07-15）：MiniMax Token Plan Key 可列出模型；晨间批次处理 10 条窗口内候选并成功；午间批次处理 2 条窗口内候选并成功；失败模拟未覆盖成功的 `delivery/current/`。MiniMax 抽取实际使用 `thinking.disabled`，以避免推理输出挤占结构化 JSON 的预算。
- 已确认的外部边界：当前 `KIMI_API_KEY` 是 Kimi For Coding 会员 Key，不能调用 Moonshot 开放平台 `https://api.moonshot.cn/v1`；它应使用 Kimi Code 的 OpenAI 兼容端点 `https://api.kimi.com/coding/v1` 和模型 `kimi-for-coding`。该模型只接受 `temperature: 1`，因此路由配置显式覆盖共享客户端默认值。2026-07-15 的本地条件仲裁已成功；Kimi 在 MVP 中仍只处理高优先级歧义项。
- 尚待 G3 验证：GitHub Secrets 注入、公开 Raw 读取、晨/午真实云端批次、失败批次保护和 Actions 日志中的无敏感信息检查。

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

## 待确认的 G4 调研边界

建议保留 GitHub Actions/MiniMax 的固定高可信来源采集、状态维护和去重责任；ChatGPT 追加高价值定向研究、官方核验与少量 `GPT 定向补录`。它不应无边界地重做全网抓取，否则会绕开 GitHub 的历史状态并重新引入重复。该调整待铭哥确认后写入 G4 任务规则。
