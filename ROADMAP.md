# ROADMAP

## 已完成

- Python runtime 主线建立
- CLI-first 主入口收敛
- 统一 slash command 层
- 工具注册、执行、审计和截断
- Bash / PowerShell 安全策略
- 会话报告和正常退出保存
- Skill 系统：项目级 `.weaver/skills`
- MCP 系统：项目根目录 `.mcp.json`
- Skill/MCP 的 Claude Code 风格命令展示
- Textual 增强界面
- 普通 CLI 已加入复古终端风格彩色分层 WEAVER FIELD OPS 启动 banner、彩色 slash command 导航、用户消息块、输入分隔线和 token/context 状态行；交互回车后会清掉原始输入行，只保留上推后的无标题用户消息块；slash command 与普通 prompt 统一渲染，并兼容管道输入前导 UTF-8 BOM
- gateway 兼容路径
- SecurityContext / EvidenceStore / writeup 草稿
- `/target`、`/note`、`/evidence`、`/writeup` CTF/lab slash commands
- session report 已包含 target、phase、evidence 和 next action
- CLI 运行状态行已显示 lab context
- OpenAI-compatible streaming chunk 合并已支持分片 tool_calls、缺省 call id、reasoning_content replay、最终 content fallback、`stream_options.include_usage` 和 usage fallback 估算
- system prompt 已按 Claude Code 风格思路拆分为中文友好的确认优先 sections
- 基础 smoke 验证

## 现在要继续做的

### P0

- 继续稳定 OpenAI-compatible streaming / tool_calls 主路径
- 完善 CTF/lab target、evidence、writeup 的最小闭环体验
- 完善权限确认策略和授权 scope 提示，让 prompt、工具策略和 transcript 行为保持一致
- 继续收敛本地配置与敏感信息边界
- 把根目录文档维持为当前真实状态

### P1

- AgentTool / sub-agent
- MCP resources / prompts
- HTTP / SSE / OAuth MCP transport
- 上下文压缩与长会话恢复
- session persistence

### P2

- Claude Messages API 原生 streaming 兼容增强
- 更完整的 pentest workflow
- scope / allowlist / checkpoint 工作流
- evidence / report 进一步结构化
- Skill 管理增强
- MCP 管理增强

## 明确非目标

- 不把 Weaver 做成无 scope、无授权确认、无审计记录的自动化攻击器
- 不在当前阶段完整复制 Claude Code 的 prompt cache、override/append layer 或 agent-specific prompt runtime
- 不把 TUI 扩展成与 CLI 并列的第二产品线

## 维护规则

每次完成用户可见修改后，同步更新：

- `README.md`
- `PROJECT_OVERVIEW.md`
- `ROADMAP.md`
- `HANDOFF.md`
- `CLAUDE.md`

如果只是内部实现小改动，也至少更新 `HANDOFF.md` 和 `CLAUDE.md` 中的当前进度。
