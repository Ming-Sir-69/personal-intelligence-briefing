# Personal Intelligence Briefing｜全流程安全审查

审查日期：2026-07-16

基线提交：`4d2d6a8`

修复分支：`fix/full-flow-security`

## 30 秒结论

未发现仍未处理的高危或严重代码漏洞。此次审查修复了外部 XML、模型响应、错误日志、GPT 搜索合同和 GitHub Actions 供应链中的 5 组中等风险，并补齐了 MiniMax → 历史召回 → Kimi 仲裁 → GPT 候选交付的集成测试。

当前代码级验证结果：

- 单元与集成测试：`82 passed`
- 分支覆盖率：`96%`
- Bandit：`0` 个发现
- pip-audit：未发现已知依赖漏洞
- GitHub Secret Scanning：`0` 个未关闭告警
- Git 历史高风险凭据模式扫描：`0` 个匹配

下午的真实定时批次仍是独立的运行时验收项；它不由离线测试替代。

## 审查范围

- RSS/Atom 公共信息采集
- XML 解析与响应体资源限制
- MiniMax 结构化抽取
- Kimi 条件仲裁
- 历史去重与失败保护
- GPT 二次研究合同与提示注入边界
- archive/current/data 持久化
- GitHub Actions 权限、Secrets 和依赖供应链
- Git 历史与 GitHub Secret Scanning

## 已修复项

### SEC-001｜外部 XML 与响应体缺少强制资源边界｜中

影响：恶意或异常 Feed/模型响应可能造成内存消耗；标准库 `ElementTree` 不适合直接解析不可信 XML。

修复：

- Feed 和模型响应均限制为 2 MB；
- RSS/Atom 使用 `defusedxml`；
- 显式拒绝 DTD/ENTITY；
- Feed 与 API 端点必须为无内嵌凭据的 HTTPS；
- Feed 条目中的非 HTTPS 链接不进入候选。

代码：`collectors.py:18-29,96-139`，`llm.py:31-74`，`config.py:20-54`。

依据：[Python XML 安全警告](https://docs.python.org/3/library/xml.etree.elementtree.html)、[Python XML vulnerabilities](https://docs.python.org/3/library/xml.html#xml-vulnerabilities)。

### SEC-002｜定时工作流把模型 Key 暴露给整个 Job｜中

影响：安装、测试和其他步骤本不需要模型 Key；Job 级环境变量扩大了凭据暴露面。

修复：仅 `Run live batch` 步骤接收 `MINIMAX_FOR_CODING_API_KEY` 和 `KIMI_API_KEY`。测试工作流继续只有 `contents: read`，运行工作流仅为提交公开产物保留 `contents: write`。

代码：`morning-briefing.yml:15-32`、`noon-briefing.yml:15-32`、`tests.yml:8-21`。

### SEC-003｜GitHub Actions 使用可移动标签｜中

影响：`@v4`、`@v5` 可被标签移动；具备 Secrets 与写权限的工作流应使用不可变引用。

修复：四份工作流均固定到 GitHub 官方仓库中已验证签名的完整提交 SHA：

- `actions/checkout`：`df4cb1c069e1874edd31b4311f1884172cec0e10`（v6.0.3）
- `actions/setup-python`：`ece7cb06caefa5fff74198d8649806c4678c61a1`（v6）

依据：[GitHub Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)。

### SEC-004｜模型字段与 GPT 查询种子边界不足｜中

影响：非标量枚举会触发未捕获的 `TypeError`；超长字段和换行/引号可扩大持久化内容并污染 GPT 查询。

修复：

- `fact_type`、`importance` 先校验类型再校验枚举；
- 事件核心字段设置长度上限并保留一次重试；
- GPT 查询种子移除控制符、引号和反斜杠并限制长度；
- 明确“每候选最多 2 次、整批晨间 12 次/午间 8 次”的搜索预算。

代码：`llm.py:189-215`、`gpt_review.py:30-41,101-108`。

### SEC-005｜异常原文可能写入公开仓库｜中

影响：第三方异常文本可能包含响应片段、路径或未来新增的敏感数据。

修复：采集和模型错误只持久化来源 ID、事件 ID与异常类型，不持久化第三方异常原文或 HTTP 响应正文。

代码：`collectors.py:58-70`、`pipeline.py:61-73`。

## 补齐的测试

1. MiniMax 非标量枚举、字段超长、重试与失败审计；
2. Feed/模型响应超限；
3. 恶意 XML 实体与非 HTTPS URL；
4. provider 异常文本和双模型 Key 不进入任何公开状态文件；
5. GPT 查询种子净化、候选级与批次级查询预算；
6. 风险候选进入 `review_level=required`；
7. MiniMax → 历史相似事件 → Kimi 条件仲裁 → `substantive_update` 全链路；
8. 四份工作流完整 SHA、密钥最小作用域、禁止高权限 Fork 触发器；
9. 既有 success/partial/failed、current 保护、handoff 去重继续回归。

## 仓库设置审计

已确认：

- 仓库为 Public；
- Secret Scanning 已启用；
- Push Protection 已启用；
- 当前无 Secret Scanning 未关闭告警；
- 当前所有工作流都显式声明 `permissions`。

## 剩余风险与建议

### R-001｜master 暂无 Ruleset/分支保护｜低，MVP 暂接受

这是单用户项目，且定时任务当前直接向 `master` 写入公开状态。强制 PR 会破坏现有自动写入，除非为 Actions 设计绕过或改用独立状态分支。MVP 先保留，流水线稳定后再拆分“代码分支”和“状态分支”。

### R-002｜仓库默认 GITHUB_TOKEN 仍为 write 且允许 Actions 批准 PR｜低

现有四份工作流均显式覆盖权限，因此当前执行不依赖默认值。建议确认本 PR 合并和一次真实批次成功后，将仓库默认权限改为 `read`，并关闭 Actions 批准 PR。

### R-003｜Dependabot 漏洞告警与安全更新未启用｜低

本次 `pip-audit` 未发现已知漏洞，但持续监控尚未启用。建议开启 Dependabot alerts/security updates。

### R-004｜仓库策略尚未强制完整 SHA｜低

当前文件已全部固定完整 SHA，但仓库设置仍允许未来提交可移动标签。建议本 PR 合并并通过 CI 后，再启用 `Require actions to be pinned to a full-length commit SHA`。

### R-005｜Python 依赖尚无带哈希锁文件｜低

当前依赖少、审计为零漏洞，MVP 暂不引入额外包管理链路。后续若来源或依赖增加，再引入带哈希的 CI 依赖锁。

### R-006｜GPT 层仍需遵守不可信输入合同｜低

代码已净化搜索种子并限制搜索预算，但不能从根本上消除公共网页的提示注入。ChatGPT 计划任务必须继续把候选、网页和搜索结果视为不可信数据，只提取事实，不执行其中指令。

## 合并后最低验收

1. CI 使用固定 SHA 成功安装 Python 和依赖；
2. 一次真实晨间或午间批次成功；
3. 公开产物中不存在 Key、Authorization 或异常正文；
4. `current` 只在 success 时更新；
5. ChatGPT 读取新候选包时遵守整批查询预算。
