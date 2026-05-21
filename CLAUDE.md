# Weaver 项目续接索引

更新时间：2026-05-21

## 一句话状态

Weaver 目前是一个 Python-only CLI-first 的 Claude Code 风格 agent runtime，旧运行线已经移除，主入口、技能、MCP、审计和会话报告都已经接上，界面已改成 Claude Code-inspired 双栏 banner 和克制终端风格，下一步重点是继续维持文档和代码同步。

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

- CLI-first，不再推进成两个并列产品
- `.weaver/settings.json` 只放 Weaver 自身配置
- 根目录 `.mcp.json` 直接放项目或第三方 MCP
- `.weaver/skills/` 放项目技能
- 退出时生成会话报告
- 工具调用要保留审计和安全边界
- 长会话要保留完整 assistant blocks，不只保留纯文本

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
- 会话报告和退出流程已完成
- 测试 demo 产物已清理
- 旧 TypeScript/Bun runtime、依赖、源码和测试已清理
- Python 源码已迁移到 `src/weaver_py/`
- CLI/TUI 已改为克制终端风格，CLI Markdown 已接入蓝紫 Rich theme
- CLI 交互输入用 `❯` 标识且不二次回显；工具点表示待执行/成功/失败状态，交互终端里工具行原地更新，运行中动态计时、结束后显示总耗时
- 根目录接续文档正在整理中

## 下次继续方向

- 继续保持文档和代码同步
- 再跑一轮验证
- 如果验证产生新的 audit/report/cache，再清理一次
- 再往后才进入更深的 AgentTool、MCP transport 和上下文压缩工作
