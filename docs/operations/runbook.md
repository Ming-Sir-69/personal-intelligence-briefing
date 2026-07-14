# 阶段交接与项目记忆

## 当前状态

- 当前阶段：G2 验收修复，G3 尚未启动。
- 最近验收：ChatGPT G2 只读验收为“有条件通过”。
- 已关闭的 G3 前置问题：四档召回、未知事件时间、批次状态、跨批次 `recent-events.json`。
- 尚待 G3 验证：工作流、Secrets 注入、公开 Raw 读取、晨/午真实批次、失败批次保护。

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

## 待确认的 G4 调研边界

建议保留 GitHub Actions/MiniMax 的固定高可信来源采集、状态维护和去重责任；ChatGPT 追加高价值定向研究、官方核验与少量 `GPT 定向补录`。它不应无边界地重做全网抓取，否则会绕开 GitHub 的历史状态并重新引入重复。该调整待铭哥确认后写入 G4 任务规则。
