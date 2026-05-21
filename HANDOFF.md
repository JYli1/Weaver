# HANDOFF

更新时间：2026-05-21

## 当前状态

Weaver 现在的主线是 Python CLI-first runtime，仓库里已经不再保留旧的 TypeScript/Bun 运行线。主入口围绕 `weaver_py.cli`，源码已迁到 `src/weaver_py/`，CLI transcript、Skill、MCP、审计、会话报告和基础 TUI 增强都已经接上；界面改为 Claude Code-inspired 双栏 banner 和克制终端风格，蓝紫主要用于 Markdown 与少量强调。

## 这次已经完成的事

- 清理了测试 demo 和临时运行产物
- 删除了测试用 Skill / MCP 文件
- 删除了旧实现及相关依赖/源码/测试/文档
- 收敛了 `.mcp.json` 的运行时位置
- 补了少量关键注释
- 自然化了一些用户可见文案
- 增加了 Weaver 自有双栏 banner、CLI Rich Markdown theme，并把整体界面收回到克制终端配色
- 调整了 CLI transcript：交互输入不二次回显，工具点表示待执行/成功/失败状态，交互终端里工具行原地更新，运行中动态计时、结束后显示总耗时
- 开始补根目录接续文档

## 当前配置约定

- `.weaver/settings.json`：Weaver 自身配置
- `.mcp.json`：项目或第三方 MCP
- `.weaver/skills/`：项目技能
- `CLAUDE.md`：接续索引和工作约定

## 下次继续的优先级

1. 保持根目录文档和真实代码同步
2. 继续收尾 README / OVERVIEW / ROADMAP / CLAUDE
3. 跑验证
4. 如验证生成新产物，再清一次

## 读文件顺序建议

下次开始时先读：

1. `README.md`
2. `PROJECT_OVERVIEW.md`
3. `ROADMAP.md`
4. `HANDOFF.md`
5. `CLAUDE.md`

## 注意事项

- 不要把 key、audit、report、cache 写进版本库
- 不要把测试 demo 重新带回来
- 不要让文档和当前代码状态脱节
