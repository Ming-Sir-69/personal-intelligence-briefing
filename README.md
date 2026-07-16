# Personal Intelligence Briefing

个人智能情报与持续学习系统。

MVP 聚焦 AI 行业实时信息：GitHub Actions 维护可追溯的候选事件与去重状态，ChatGPT 计划任务完成最终审稿与定向查漏。GitHub Pages 将当前成功批次转换成无需授权的普通 HTML，供 ChatGPT、Perplexity、Grok、Trae Solo 等网页读取型 Agent 审核。

## 公开只读入口

- 首页：<https://ming-sir-69.github.io/personal-intelligence-briefing/>
- 当前状态：<https://ming-sir-69.github.io/personal-intelligence-briefing/current/status/>
- 晨间审核：<https://ming-sir-69.github.io/personal-intelligence-briefing/current/morning/>
- 午间审核：<https://ming-sir-69.github.io/personal-intelligence-briefing/current/noon/>

`delivery/current/*.json` 仍是唯一正式状态源；`docs/current/` 只是确定性生成的公开只读展示层。下游 Agent 必须以页面正文中的 `batch_id`、`generated_at` 和 `source_commit_sha` 判断新鲜度，不能用旧内容填充失败批次。

本地生成：

```bash
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
