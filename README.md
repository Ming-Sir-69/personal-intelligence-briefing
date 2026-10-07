# Personal Intelligence Briefing

个人智能情报与持续学习系统。

MVP 聚焦 AI 行业实时信息：GitHub Actions 维护可追溯的候选事件与去重状态，ChatGPT 计划任务完成最终审稿与定向查漏。GitHub Pages 将当前成功批次转换成无需授权的普通 HTML，供 ChatGPT、Perplexity、Grok、Trae Solo 等网页读取型 Agent 审核。

## 适合谁与阅读顺序

适合持续跟踪公开 AI 行业信息的个人用户，以及需要审核可追溯候选事件的网页读取型 Agent。先查看「当前状态」，再进入相应晨间或午间审核页；页面提供的批次字段用于判断时效与来源。

代码与依赖配置见 [pyproject.toml](pyproject.toml)、[src/intelligence_briefing/](src/intelligence_briefing/)；页面生成入口为 [scripts/build_public_pages.py](scripts/build_public_pages.py)。事件处理、报告选择与模型路由配置位于 [config/](config/)。

当前项目版本为 `0.1.0`，范围聚焦公开 AI 行业候选信息；候选整理与最终审稿是不同环节。公开页面的可用性以 GitHub Pages 当前部署状态为准，失败批次与内容新鲜度按下方边界判断。

## 公开只读入口

- 首页：<https://ming-sir-69.github.io/personal-intelligence-briefing/>
- 当前状态：<https://ming-sir-69.github.io/personal-intelligence-briefing/current/status/>
- 晨间审核：<https://ming-sir-69.github.io/personal-intelligence-briefing/current/morning/>
- 午间审核：<https://ming-sir-69.github.io/personal-intelligence-briefing/current/noon/>

`delivery/current/*.json` 仍是唯一正式状态源；`docs/current/` 只是确定性生成的公开只读展示层。下游 Agent 必须以页面正文中的 `batch_id`、`generated_at` 和 `source_commit_sha` 判断新鲜度，不能用旧内容填充失败批次。

在仓库根目录本地生成展示页，需要 Python 3.12 或更高版本，并先安装项目依赖（建议使用独立虚拟环境）。安装后使用同一环境执行脚本：

```bash
python -m pip install -e .
python scripts/build_public_pages.py --root "$PWD"
```

GitHub Pages 需要在仓库 `Settings → Pages` 将 Source 选择为 `GitHub Actions`。晨间、午间或手动 live 工作流只有在 `docs/` 真实变化时才上传并部署页面；Pages 部署 job 与模型调用 job 权限隔离，不接收 MiniMax/Kimi Secrets。

## 安全边界

- 仅处理公开互联网信息。
- 不提交 API Key、Cookie、个人隐私、公司或客户资料。
- 模型密钥仅从 GitHub Actions Secrets 读取。
- HTML页面不提供写入能力，不新增数据库、API服务、Secret或第三方脚本。
- 动态字段全部转义并经过密钥样式扫描；失败或部分成功批次不会替换上一份成功页面。

详细产品设计见 `docs/superpowers/specs/`。


## 贡献与维护

欢迎通过 Issue 或 Pull Request 补充公开来源、改进去重与审稿说明、修正页面展示问题。请提供公开来源链接与可复现的最小样例，说明受影响的时间窗口或批次字段；凭据、私人资料与内部数据无需上传。

仓库维护：[Ming-Sir-69](https://github.com/Ming-Sir-69)。当前没有 LICENSE 或 NOTICE，代码与文档的复用许可待确认。
