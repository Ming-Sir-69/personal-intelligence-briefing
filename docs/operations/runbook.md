# 阶段交接与项目记忆

## 当前状态

- 当前阶段：G1—G3 与 G4 接入实现已完成，进入自然调度观察期。GitHub Actions、历史去重、MiniMax/Kimi 条件路由、公开 Pages 审核入口和 ChatGPT 晨报/午报任务均已部署；下一门槛是验证完整的自然定时链路，而不是继续增加功能。
- 最近验收：PR #11（全流程安全加固）与 PR #12（GitHub Pages 公开审核入口）已合并；`master` 午间 live 批次和 Pages 部署成功。无登录普通网页读取验收已确认首页、状态页和午间页直接返回 HTML 正文，批次字段一致且 `review_status=ready`。
- 已关闭的 G3 前置问题：四档召回、未知事件时间、批次状态、跨批次 `recent-events.json`。
- G3 已实现：测试、手动运行、晨间/午间工作流；成功批次水位线；按来源隔离的采集错误；离线失败/部分失败模拟。
- 已完成本地真实验证（2026-07-15）：MiniMax Token Plan Key 可列出模型；晨间批次处理 10 条窗口内候选并成功；午间批次处理 2 条窗口内候选并成功；失败模拟未覆盖成功的 `delivery/current/`。MiniMax 抽取实际使用 `thinking.disabled`，以避免推理输出挤占结构化 JSON 的预算。
- 已确认的外部边界：当前 `KIMI_API_KEY` 是 Kimi For Coding 会员 Key，不能调用 Moonshot 开放平台 `https://api.moonshot.cn/v1`；它应使用 Kimi Code 的 OpenAI 兼容端点 `https://api.kimi.com/coding/v1` 和模型 `kimi-for-coding`。该模型只接受 `temperature: 1`，因此路由配置显式覆盖共享客户端默认值。2026-07-15 的本地条件仲裁已成功；Kimi 在 MVP 中仍只处理高优先级歧义项。
- 已完成 G3 云端验证：GitHub Secrets 成功注入且日志以 `***` 掩码显示；晨/午 live 批次均生成 `success` 交付；失败模拟仅新增 failed archive，未覆盖 `delivery/current/`；三个固定公开 Raw 入口均返回 HTTP 200。
- 已完成 G4 任务配置：ChatGPT 晨报和午报保持启用，分别在北京时间 07:30 与 13:30 运行。两项提示词已改为只读取 GitHub Pages 的状态页与对应时段页，不依赖 GitHub 连接器、API、CLI、Raw/CDN、登录或 Token；晨间官方源查漏上限 4 次、补录 3 条，午间分别为 3 次与 2 条，扩散最多一层。

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

## GitHub Pages 跨平台审核入口

### 状态边界

- `delivery/current/*.json` 是唯一正式状态源；`docs/current/` 只显示这些JSON的确定性HTML快照。
- manifest只有在 `status == success` 且 `kind` 与晨间或午间入口匹配时，页面才标记为 `review_status: ready`。
- kind不匹配的入口明确显示 `unavailable`，不读取对应旧候选或历史事件。
- failed或partial批次不能覆盖 `delivery/current/`；静态生成器检测到非成功manifest且已有成功页面时，也不会替换该公开快照。
- 页面没有写入接口，不接收ChatGPT、Perplexity、Grok或Trae Solo的审核结果。

### 本地生成与验证

```bash
source .venv/bin/activate
python scripts/build_public_pages.py --root "$PWD"
python -m pytest tests/test_public_pages.py tests/test_workflows.py -q
```

输出位置：

- `docs/index.html`
- `docs/current/status/index.html`
- `docs/current/morning/index.html`
- `docs/current/noon/index.html`
- `docs/assets/style.css`

页面正文直接包含审核字段，不依赖JavaScript。每次成功批次在同一工作区内先生成JSON、再生成HTML，校验全部通过后由同一提交写入 `data/`、`delivery/` 和 `docs/`。页面构建失败时提交步骤不会执行，仓库中的上一份成功JSON和HTML保持一致。

### 启用GitHub Pages

合并包含静态页面与部署工作流的PR后，在仓库中打开：

1. `Settings → Pages`；
2. Source选择 `GitHub Actions`；
3. 保存；
4. 在默认分支手动运行一次 `Manual briefing batch` 的 `live`，或等待下一次晨间/午间任务；
5. 确认同一次工作流中的 `deploy_pages` job 成功后，等待 GitHub Pages 首次发布。

不能使用 `Deploy from a branch → master → /docs` 作为长期自动发布方案：晨间和午间工作流使用 `GITHUB_TOKEN` 提交新JSON与HTML，而此类自动提交不会触发分支式Pages构建。当前工作流改为在生成阶段检测 `docs/` 变化并上传官方Pages artifact，再由独立部署job发布。

部署安全边界：

- 生成job只保留现有 `contents: write`；
- 部署job只拥有 `contents: read`、`pages: write`、`id-token: write`；
- MiniMax/Kimi Secrets只注入 `Run live batch`，不进入页面上传或部署步骤；
- failed、partial、dry-run或HTML无变化时，不上传也不部署页面；
- 官方Pages Actions固定到完整commit SHA。

预计公开地址：

- <https://ming-sir-69.github.io/personal-intelligence-briefing/>
- <https://ming-sir-69.github.io/personal-intelligence-briefing/current/status/>
- <https://ming-sir-69.github.io/personal-intelligence-briefing/current/morning/>
- <https://ming-sir-69.github.io/personal-intelligence-briefing/current/noon/>

使用无登录浏览器或任意网页读取型Agent验证HTTP可访问后，再把这些URL替换进对应平台提示词。验收不能以GitHub API、GitHub连接器、Raw链接或已登录仓库页面替代普通网页正文。Agent必须先核对 `batch_id`、`generated_at`、`source_commit_sha` 和 `review_status`；若页面不可审核或时间过旧，应报告上游不可用，不得补入旧闻。

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

## 2026-07-16 G4 二次研究契约真实验证

- PR #10 合并提交为 `3523812`。手动晨间 live [run 29458938350](https://github.com/Ming-Sir-69/personal-intelligence-briefing/actions/runs/29458938350) 生成批次 `morning-20260716T073438+0800`，状态为 `success`；候选包输出晨间补录上限 3、官方源查漏查询上限 4、最大扩散一层。
- 手动午间 live [run 29459013203](https://github.com/Ming-Sir-69/personal-intelligence-briefing/actions/runs/29459013203) 生成批次 `noon-20260716T073606+0800`，状态为 `success`；候选包输出午间补录上限 2、官方源查漏查询上限 3、最大扩散一层。
- 两个批次各处理 2 条输入并均被成功 handoff 历史判为重复，因此 `candidate_reviews` 为空，没有人为制造新闻验证 `required`。该路径已有回归测试；下一条真实新增、未确定、高重要性或带标准化标记的候选必须进入 `required`，再作为计划任务自然运行验收。
- 晨间真实审计记录 2 次 `feed_time_metadata` 和 1 次 `model_retry`；午间记录 1 次 `model_retry`。两个批次的 `counts` 均保持纯整数，公开 archive、current 和 run 文件未发现 Authorization、Bearer Token、API Key 值或环境变量值。

## 2026-07-16 G4 公开入口与计划任务最终配置

- PR #11 合并提交为 `187791e`，完成 RSS/XML、模型响应、持久化错误、Actions 版本固定和 Secret 注入范围的安全加固。
- PR #12 合并提交为 `e3dfb18`，完成服务器直接返回正文的首页、状态页、晨间页和午间页，以及与状态工作流同链路的 Pages artifact 发布。
- `master` 午间 live [run 29485504368](https://github.com/Ming-Sir-69/personal-intelligence-briefing/actions/runs/29485504368) 生成批次 `noon-20260716T170024+0800`；运行、Pages artifact 上传和 `deploy_pages` 均成功，状态提交为 `7278813`。
- 无登录普通网页验收确认以下入口首次访问即返回 HTML 正文，不需要 JavaScript、GitHub 连接器、API、CLI、Raw、Token 或登录：
  - <https://ming-sir-69.github.io/personal-intelligence-briefing/>
  - <https://ming-sir-69.github.io/personal-intelligence-briefing/current/status/>
  - <https://ming-sir-69.github.io/personal-intelligence-briefing/current/morning/>
  - <https://ming-sir-69.github.io/personal-intelligence-briefing/current/noon/>
- ChatGPT 账户中的两个计划任务保持启用：晨报每天 07:30，午报每天 13:30（北京时间）。提示词只读取状态页与对应时段页；若页面不可读、批次不一致、kind 错误、状态非 success 或 `review_status` 非 ready，则停止审核且不得用旧闻或独立搜索替代。
- 页面疑似缓存不一致时，只允许以状态页 `batch_id` 给对应时段页追加一次 `?batch=<batch_id>` 重试。通过门禁后才执行页面内的 `gpt_review_plan`：晨间官方源查漏总查询不超过 4 次、补录不超过 3 条；午间分别不超过 3 次和 2 条；扩散最多一层。

## 自然调度验收门槛

首次完整自然调度应按以下顺序验收，手动 `workflow_dispatch` 成功不能替代这项证据：

| 时段 | 上游计划 | 下游计划 | 必须确认 |
| --- | --- | --- | --- |
| 晨间 | GitHub Actions 06:20 | ChatGPT 07:30 | schedule 触发、批次成功、状态提交、Pages 部署、晨间页 ready、ChatGPT 使用同一新鲜批次并完成有界审核 |
| 午间 | GitHub Actions 12:20 | ChatGPT 13:30 | schedule 触发、增量范围连续、批次成功、Pages 部署、午间页 ready、ChatGPT 不重复晨间内容 |

每次验收至少记录：workflow run URL/ID、`batch_id`、`scheduled_for`、`actual_started_at`、`completed_at`、`source_commit_sha`、Pages `review_status`、ChatGPT 输出结果，以及是否存在上游错误、缓存错配、重复或密钥样式泄漏。

当前仍待真实运行确认：

1. GitHub schedule 的实际延迟和 Pages 发布耗时能否稳定落在 07:30 / 13:30 前的缓冲内；
2. ChatGPT Scheduled Tasks 的无人值守环境能否持续读取公开 Pages，而不是只在普通新对话中成功；
3. 下一条真实新增、高重要性、不确定或带标准化标记的候选是否进入 `review_level=required`，并按查询预算完成核验；
4. Kimi 条件仲裁在云端自然批次中的首次真实触发是否保持正确路由、结构化结果与低用量；
5. 连续一周运行后的重复率、漏报、低价值项、官方一手来源覆盖率、上游失败率和实际阅读时长。

没有高价值新增不是失败；只要批次、页面与审核链路正确，最终输出“本批次无高价值新增”即视为有效交付。若自然批次失败，优先修复状态连续性、Pages 新鲜度、去重或 Secret 边界，不用手动制造新闻验证内容质量。

## 后续开发方向

按真实运行证据推进，避免在自然调度尚未稳定前扩大范围：

### 近期：G4 一周观察与最小修复

- 建立按批次的重复、补录、删除、修正、上游错误和阅读反馈记录；
- 对连续 Codex alpha / prerelease 版本流增加事件族降噪，仅在稳定版、实质功能、安全或兼容变化时再次推送；
- 根据一周数据调整来源、重要性阈值、查询预算和报告长度，不预先增加复杂模型限额。

### 第二阶段：受控扩展

- AI HOT 先走匿名只读 API 小样本 POC，比较覆盖率、重复率、时效和署名/canonical 合同；暂不安装 MCP、不新增 Secret；
- 为 ChatGPT 审核反馈设计受限写回通道，只允许提交结构化反馈文件，由 Actions 或 Codex 验证后进入正式状态；不允许 ChatGPT 直接修改事件库、代码、工作流或 Secrets；
- 增加周报、月度知识汇编、来源质量评分和人工反馈闭环；PDF/Word 仅在 Markdown/HTML 稳定后生成；
- 需要个人阅读记录、工作项目映射或生活反思时，另建私有上下文仓库，不写入当前公开仓库。

### 长期学习模块

- 组织机制、数字化工具与权力关系：每周两次案例学习；
- 宏观经济与国际政治经济：每周 2—3 次通勤/运动音频推荐；
- 脑神经科学与个人效率：每日极简自检、每周一次正式方法复盘；
- 长期学习任务与 07:30 / 13:30 AI 实时雷达保持独立，避免挤占实时报告和重复去重链路。
