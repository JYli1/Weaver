# ROADMAP

## 已完成

- Python runtime 主线建立
- CLI-first 主入口收敛
- 统一 slash command 层
- 工具注册、执行、审计和截断
- Bash 安全策略
- 会话报告和正常退出保存
- Skill 系统：项目级 `.weaver/skills`
- MCP 系统：项目根目录 `.mcp.json`
- Skill/MCP 的 Claude Code 风格命令展示
- Textual 增强界面
- Weaver 自有双栏 banner、克制终端 UI、蓝紫 Rich Markdown 渲染主题和三态工具 transcript
- gateway 兼容路径
- 基础 smoke 验证

## 现在要继续做的

### P0

- 补齐 Claude Messages API 原生 streaming 的完整路径
- 完善权限确认策略
- 继续收敛本地配置与敏感信息边界
- 把根目录文档维持为当前真实状态

### P1

- AgentTool / sub-agent
- MCP resources / prompts
- HTTP / SSE / OAuth MCP transport
- 上下文压缩与长会话恢复
- session persistence

### P2

- 更完整的 pentest workflow
- scope / allowlist / checkpoint 工作流
- evidence / report 进一步结构化
- Skill 管理增强
- MCP 管理增强

## 明确非目标

- 未授权扫描
- DoS
- 检测规避
- 凭证滥用
- 破坏性自动化

## 维护规则

每次完成用户可见修改后，同步更新：

- `README.md`
- `PROJECT_OVERVIEW.md`
- `ROADMAP.md`
- `HANDOFF.md`
- `CLAUDE.md`

如果只是内部实现小改动，也至少更新 `HANDOFF.md` 和 `CLAUDE.md` 中的当前进度。
