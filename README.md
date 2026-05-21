# Weaver

Weaver 是一个面向**授权安全测试、防御研究、CTF/lab 和学习用途**的 Claude Code 风格 Python-only agent runtime。

当前主线是 **Python CLI-first**：大部分交互都在一个统一的命令行入口里完成；Textual/TUI 只作为局部增强界面，用于命令选择、技能管理、MCP 管理等少数需要选择器的场景。

## 当前特性

- 单一 CLI 主入口，带 Weaver 品牌 banner 和 transcript
- 更接近 Claude Code 的双栏欢迎 banner 和克制终端界面
- Rich Markdown 渲染主题，标题、代码、列表和链接使用蓝紫强调
- Claude Code 风格的 slash commands
- 工具调用展示、状态栏、阶段提示、token 统计
- 工具 transcript 使用三态点：待执行、成功、失败，交互终端里原地更新同一行
- 交互输入只显示一次，并用 `❯` 作为用户输入标识
- 运行中显示动态思考计时，结束后只保留总耗时
- 项目级 Skills：`.weaver/skills/<name>/SKILL.md`
- 项目级 MCP：根目录 `.mcp.json`
- 退出自动生成会话报告
- Bash 安全策略与工具审计日志

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
  -> ToolRegistry
  -> SkillLoader
  -> McpManager
  -> Report / Audit
```

## 安全边界

- 只用于授权范围内的测试和研究
- Bash 有安全策略
- 工具调用会记录审计日志
- 高风险动作需要确认
- 不默认支持未授权扫描、破坏性自动化、DoS 或规避检测
