# PROJECT_OVERVIEW

## 一句话概述

Weaver 是一个 Claude Code 风格的 Python-only agent runtime，源码位于 `src/weaver_py/`，用于授权安全测试、防御性研究、CTF/lab 和学习场景。

## 当前主线

- 主线语言：Python 3.11+
- 源码布局：`src/weaver_py/`
- 主入口：`weaver_py.cli`（文件位于 `src/weaver_py/cli.py`）
- 主交互形态：CLI-first
- TUI 角色：局部增强，不是另一套并列产品
- UI 风格：Claude Code-inspired 双栏 banner 和克制终端界面，CLI Markdown 使用蓝紫 Rich theme
- 旧实现：已清理，不再保留

## 架构

```text
weaver_py.cli
  -> WeaverSession
      -> AgentEngine
      -> ToolRegistry
      -> SkillLoader
      -> McpManager
      -> Report / Audit
```

## 核心模块

### `src/weaver_py/cli.py`

统一入口。负责 Weaver 自有品牌 banner、transcript 渲染、输入循环、slash commands、退出流程；交互输入用 `❯` 标识，不再二次回显。

### `src/weaver_py/runtime/session.py`

会话总控。汇总 config、engine、registry、skills、MCP、phase、tokens、session_id 和报告路径。

### `src/weaver_py/agent/engine.py`

LLM 调度层。处理消息循环、tool use、tool result、phase 更新和 gateway 兼容路径。

### `src/weaver_py/tools/registry.py`

工具注册与执行总入口。负责 schema 生成、异常包装、输出截断和审计写入。

### `src/weaver_py/skills/*`

项目技能加载、解析和渲染。当前只加载项目内 `.weaver/skills`。

### `src/weaver_py/mcp/*`

stdio MCP client、manager 和工具适配层。项目根目录 `.mcp.json` 可直接提供 MCP 配置。

### `src/weaver_py/runtime/commands.py`

slash command 注册、帮助文本和命令分发。

### `src/weaver_py/runtime/report.py`

会话报告生成与保存。

### `src/weaver_py/ui/*` 和 `src/weaver_py/tui/*`

负责 CLI transcript、banner 和 Textual 增强界面；整体 UI 保持克制终端风格，CLI Markdown 通过蓝紫 Rich theme 渲染，工具点表示待执行/成功/失败状态，交互终端里工具状态原地更新。

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
- 仍有一些 TUI 体验和报告格式可以继续打磨
