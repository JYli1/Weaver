# Weaver 项目续接索引

更新时间：2026-05-25

## 一句话状态

Weaver 目前是一个 OpenAI-compatible 优先、Python CLI-first 的 CTF/lab 安全测试 agent runtime。SecurityContext/EvidenceStore/writeup、CTF/lab slash commands、CLI lab 状态行、OpenAI-compatible streaming chunk merge、usage fallback、复古彩色 CLI UI 和中文友好的确认优先 system prompt sections 已完成，下一步重点是真实网关端到端验证、权限确认一致性和 CTF/lab 最小闭环体验打磨。

## 先读哪些文件

1. `README.md`
2. `PROJECT_OVERVIEW.md`
3. `ROADMAP.md`
4. `HANDOFF.md`
5. 当前 `CLAUDE.md`

## 当前主入口

- `python -m weaver_py.cli --cwd D:/github_project/Weaver`
- `python -m weaver_py.cli --help`
- `python -m weaver_py.cli --tui --cwd D:/github_project/Weaver`
- 源码目录现在是 `src/weaver_py/`

## 当前关键规则

- OpenAI-compatible 是主模型路径，Claude Messages API 只是兼容路径
- CLI-first，不再推进成两个并列产品
- `.weaver/settings.json` 只放 Weaver 自身配置
- 根目录 `.mcp.json` 直接放项目或第三方 MCP
- `.weaver/skills/` 放项目技能
- 退出时生成会话报告（含 target/evidence/phase/next action）
- 工具调用要保留审计和安全边界
- 长会话要保留完整 assistant blocks，不只保留纯文本
- system prompt 采用中文友好的 section 体系，安全测试行为用“确认授权、明确 scope、说明影响、再执行”表达，不堆叠禁止清单
- evidence 记录要优先引导使用 `/note`、`/evidence`、`/writeup`，不要承诺 runtime 自动落盘所有 evidence
- 所有新增或调整的配置项、配置示例、prompt section 常量和文档化配置说明，都必须有详细中文注释

## 维护要求

每次完成用户可见的修改后，必须同步更新这些文档：

- `README.md`
- `PROJECT_OVERVIEW.md`
- `ROADMAP.md`
- `HANDOFF.md`
- `CLAUDE.md`

如果这次改动只影响内部实现，也至少更新 `HANDOFF.md` 和 `CLAUDE.md`，让下次对话能接上当前真实状态。

## 当前进度记录

- Python runtime 已建立并可运行
- CLI-first 已收敛
- Skills 已接入项目级 `.weaver/skills`
- MCP 已接入项目根目录 `.mcp.json`
- 会话报告和退出流程已完成，报告含 target/phase/evidence/next action
- SecurityContext / EvidenceStore / build_writeup 已实现
- CTF/lab slash commands 已实现：`/target`、`/note`、`/evidence`、`/writeup`
- CLI 运行状态行已显示 lab context（phase、evidence count、target）
- OpenAI-compatible streaming chunk 合并已增强（分片 tool_calls、缺省 call id、按 index 排序、reasoning_content replay、最终 content fallback）
- OpenAI-compatible streaming 会请求 usage；若网关不返回 usage，会用 prompt/messages 与回复文本做保守 token 估算；若网关对 `stream_options.include_usage` 返回 400/422，会自动去掉该字段重试
- session phase/confidence 状态同步已修复（统一从 SecurityContext 回写）
- 测试 demo 产物已清理
- 旧 TypeScript/Bun runtime、依赖、源码和测试已清理
- Python 源码已迁移到 `src/weaver_py/`
- 普通 CLI 视觉已更新为复古终端风格，包含启动彩色分层 WEAVER FIELD OPS ASCII banner、彩色 slash command 导航、无标题用户消息块、底部 token/context 状态行和输入分隔线；CLI Markdown 已接入蓝紫 Rich theme
- CLI 交互输入用 `❯` 标识且不二次回显；用户 prompt 块使用 Rich cell-width helper 保证中文宽字符对齐；工具点表示待执行/成功/失败状态，交互终端里工具行原地更新，运行中动态计时、结束后显示总耗时
- CLI 底部状态行已接入当前 phase、target、evidence 数和 token 状态，并对 phase/target 做 Rich markup 转义；每轮输出后状态行留在当前 transcript 底部；交互回车后会清掉原始输入行和上一轮底部状态，非空 prompt 在 selector 和 `/mcp reload` 特殊处理决策后都会统一渲染为无标题用户消息块，slash command 也进入同一视觉流，输入开头 UTF-8 BOM 会被防御性剥离
- smoke 测试覆盖 CTF/lab、安全上下文、PowerShell、retro palette/banner/helpers、CLI exit prompt block 和 chat usage fallback
- 根目录接续文档已同步到当前真实状态
- system prompt 已完成中文友好的 section 化，覆盖身份定位、授权/scope/影响确认、渗透测试工作流、工具调用、evidence/writeup、phase tracking 和输出风格

## 下次继续方向

- 真实 OpenAI-compatible 网关端到端验证（`--gateway` smoke）
- CTF/lab 最小闭环体验打磨（scope 提示、evidence 记录引导、writeup 增强）
- 权限确认策略，让 prompt、工具执行和 transcript 保持一致
- 后续 prompt cache / override / agent-specific prompt layer
- AgentTool / sub-agent
- MCP resources / prompts / HTTP transport
- 上下文压缩与长会话恢复
