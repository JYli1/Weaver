# PROJECT_OVERVIEW

## 一句话概述

Weaver 是一个 OpenAI-compatible 优先、Claude Code 风格的 Python-only agent runtime，源码位于 `src/weaver_py/`，用于授权安全测试、防御性研究、CTF/lab 和学习场景。

## 当前主线

- 主线语言：Python 3.11+
- 源码布局：`src/weaver_py/`
- 主入口：`weaver_py.cli`（文件位于 `src/weaver_py/cli.py`）
- 主模型路径：OpenAI-compatible chat completions，重点打磨 streaming/tool_calls
- Claude 路径：Claude Messages API 兼容保留，不作为当前 P0 主线
- 主交互形态：CLI-first
- TUI 角色：局部增强，不是另一套并列产品
- UI 风格：普通 CLI 使用复古终端风格彩色分层 WEAVER FIELD OPS 启动 ASCII banner、彩色 slash command 导航、无标题用户消息块、底部 token/context 状态行和输入分隔线；Textual/TUI 仍作为局部增强界面。CLI Markdown 使用蓝紫 Rich theme
- 旧实现：已清理，不再保留

## 架构

```text
weaver_py.cli
  -> WeaverSession
      -> AgentEngine
      -> SecurityContext / EvidenceStore
      -> ToolRegistry
      -> SkillLoader
      -> McpManager
      -> Report / Writeup / Audit
```

## 核心模块

### `src/weaver_py/cli.py`

统一入口。负责 Weaver 自有品牌 banner、transcript 渲染、输入循环、slash commands、退出流程；交互输入用 `❯` 标识，回车后会清掉原始输入行，只保留上推后的无标题用户 prompt 块。用户 prompt 块使用 Rich cell-width 计算/裁剪，中文宽字符也能保持边框对齐；slash command 在分发前也会渲染成同一无标题用户消息块，PowerShell/管道输入前导 UTF-8 BOM 会被防御性剥离；底部状态行显示 ctx、input/output tokens、phase、evidence 数和 target，并在每轮输出后留在当前 transcript 底部，同时对 phase/target 动态内容做 Rich markup 转义。

### `src/weaver_py/runtime/session.py`

会话总控。汇总 config、engine、registry、skills、MCP、phase、tokens、session_id、SecurityContext、EvidenceStore 和报告路径。

### `src/weaver_py/agent/engine.py`

LLM 调度层。处理消息循环、tool use、tool result、phase 更新和 OpenAI-compatible gateway 路径；streaming chunk 会归并为普通 chat completion 响应，保证分片 tool_calls 可继续进入统一工具循环。OpenAI-compatible streaming 请求会带上 `stream_options.include_usage`，如果网关返回 400/422 会自动去掉该字段重试；如果网关不返回 usage，则用当前 prompt/messages 和回复文本做保守 token 估算，避免 CLI 底部状态行一直停在 0。system prompt 已拆分为中文友好的 section：身份定位、授权/scope/影响确认、渗透测试工作流、工具调用、evidence/writeup、phase tracking 和输出风格。

### `src/weaver_py/tools/registry.py`

工具注册与执行总入口。负责 schema 生成、异常包装、输出截断和审计写入。

### `src/weaver_py/skills/*`

项目技能加载、解析和渲染。当前只加载项目内 `.weaver/skills`。

### `src/weaver_py/mcp/*`

stdio MCP client、manager 和工具适配层。项目根目录 `.mcp.json` 可直接提供 MCP 配置。

### `src/weaver_py/runtime/commands.py`

slash command 注册、帮助文本和命令分发。

### `src/weaver_py/runtime/report.py`

会话报告生成与保存，当前报告会包含 target、phase、evidence、next action 和最近工具事件。

### `src/weaver_py/security/*`

CTF/lab 安全任务层。`SecurityContext` 维护 mode、target、phase、next action；`EvidenceStore` 记录 note/finding；`build_writeup()` 生成 writeup 草稿。

### `src/weaver_py/ui/*` 和 `src/weaver_py/tui/*`

负责 CLI transcript、banner 和 Textual 增强界面；启动 banner 的布局按纯文本 cell width 计算，输出层再加 Rich 彩色 logo 与 slash command 导航，动态路径/model/target 会先转义。整体 UI 保持克制终端风格，CLI Markdown 通过蓝紫 Rich theme 渲染，工具点表示待执行/成功/失败状态，交互终端里工具状态原地更新。

## 配置规则

### `.weaver/settings.json`

只放 Weaver 自身配置：模型、密钥、base URL、超时、报告目录、执行后端。

### `.mcp.json`

直接放项目或第三方 MCP servers。

### `.weaver/skills/`

放项目技能。

### `CLAUDE.md`

放接续索引和当前工作约定，不写长流水账。

## Claude API / gateway

- Claude 模型走 Anthropic Messages API
- 非 Claude gateway 模型走 OpenAI-compatible chat completions 路径
- 长会话和工具循环要保留完整 assistant blocks，不只保留纯文本

## 当前限制

- 还没做完整的 MCP resources/prompts
- 还没做 HTTP/SSE/OAuth MCP transport
- 还没做 AgentTool / sub-agent
- 还没做完整上下文压缩和长期会话持久化
- prompt 已完成基础 section 化，但还没做 prompt cache、override/append layer 或 agent-specific prompt layer
- 仍有一些 TUI 体验和报告格式可以继续打磨
