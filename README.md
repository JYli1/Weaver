# Weaver

Weaver 是一个面向**授权安全测试、防御研究、CTF/lab 和学习用途**的 Claude Code 风格 Python-only agent runtime。

当前主线是 **OpenAI-compatible 优先 + Python CLI-first**：默认优先打磨 OpenAI 格式模型网关的 streaming/tool_calls 体验；Claude Messages API 作为兼容路径保留。大部分交互都在一个统一的命令行入口里完成；Textual/TUI 只作为局部增强界面，用于命令选择、技能管理、MCP 管理等少数需要选择器的场景。

## 当前特性

- 单一 CLI 主入口，带 Weaver 品牌 banner 和 transcript
- 复古终端风格 CLI：启动彩色分层 WEAVER FIELD OPS ASCII banner、彩色 slash command 导航、无标题用户消息块、底部 token/context 状态行和输入分隔线
- Rich Markdown 渲染主题，标题、代码、列表和链接使用蓝紫强调
- Claude Code 风格的 slash commands
- CTF/lab 工作流：`/target`、`/note`、`/evidence`、`/writeup`
- 工具调用展示、lab 状态栏、阶段提示、token 统计
- 底部状态行显示 ctx、input/output tokens、phase、evidence 数和 target，并在每轮输出后留在当前 transcript 底部；OpenAI-compatible streaming 会请求 usage，网关不返回 usage 时使用保守估算，动态字段会做 Rich markup 转义
- 工具 transcript 使用三态点：待执行、成功、失败，交互终端里原地更新同一行
- 交互输入用 `❯` 作为用户输入标识；回车后原始输入行会被清掉，只保留上推后的无标题用户 prompt 块；用户 prompt 块按终端 cell width 渲染，兼容中文宽字符；slash command 也会先进入同一无标题用户消息块再执行
- 运行中用稳定低频计时显示当前耗时，结束后只保留总耗时
- 项目级 Skills：`.weaver/skills/<name>/SKILL.md`
- 项目级 MCP：根目录 `.mcp.json`
- 退出自动生成会话报告，报告里包含 target、phase、evidence 和 next action
- OpenAI-compatible SSE chunk 合并，支持分片 tool_calls、缺省 call id、reasoning_content replay、最终 content fallback 和 usage fallback
- 中文友好的渗透测试 agent system prompt，按身份、授权确认、工作流、工具调用、evidence/writeup 和输出风格拆分 section
- Bash / PowerShell 安全策略与工具审计日志

## 安装

需要 Python 3.11+。

```bash
python -m pip install -e D:/github_project/Weaver
```

## 运行

```bash
python -m weaver_py.cli --cwd D:/github_project/Weaver
```

常用参数：

```bash
python -m weaver_py.cli --help
python -m weaver_py.cli --tui --cwd D:/github_project/Weaver
```

## 配置

### Weaver 本地配置

`./.weaver/settings.json` 只放 Weaver 自身配置：

- `api_key` / `api_key_helper`
- `model`
- `base_url`
- `custom_headers`
- `timeout`
- `reports_dir`
- `backend`

### MCP 配置

根目录 `./.mcp.json` 直接提供项目或第三方 MCP servers。

### Skills

项目技能放在 `./.weaver/skills/<name>/SKILL.md`。

## 常用 slash commands

- `/status`：显示当前会话状态
- `/clear`：清空界面和当前会话
- `/report`：生成本次会话报告
- `/tools`：显示当前可用工具
- `/skills`：查看和重载 skills
- `/mcp`：查看和重载 MCP 服务器
- `/permissions`：显示当前权限和安全策略
- `/target <value>`：设置当前 CTF/lab target
- `/note <text>`：把当前发现记录为 note/evidence
- `/evidence`：查看当前 evidence
- `/writeup`：生成 CTF/lab writeup 草稿
- `/init`：显示初始化和迁移说明
- `/help`：显示帮助信息
- `/exit` / `/quit` / `exit` / `quit`：正常退出并保存会话报告

## 验证

```bash
python -m compileall -q D:/github_project/Weaver/src/weaver_py
python D:/github_project/Weaver/tests/smoke_python_runtime.py
python -m weaver_py.cli --help
```

## 架构概览

```text
CLI / TUI
  -> WeaverSession
      -> AgentEngine
      -> SecurityContext / EvidenceStore
      -> ToolRegistry
      -> SkillLoader
      -> McpManager
      -> Report / Writeup / Audit
```

## 安全边界

- Weaver 面向授权范围内的安全测试、防御研究、CTF/lab 和学习用途
- system prompt 采用“确认授权、明确 scope、说明影响、再执行”的表达方式，而不是堆叠禁止清单
- Bash / PowerShell 等工具保留安全策略、审计日志和高影响动作确认
- evidence 不承诺自动落盘；需要保留关键信息时，优先使用 `/note`、`/evidence`、`/writeup` 维护闭环
