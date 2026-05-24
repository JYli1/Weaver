# HANDOFF

更新时间：2026-05-25

## 当前状态

Weaver 现在的主线是 OpenAI-compatible 优先、Python CLI-first CTF/lab agent runtime。主入口围绕 `weaver_py.cli`，源码位于 `src/weaver_py/`。CLI transcript、Skill、MCP、审计、会话报告、SecurityContext/EvidenceStore/writeup、CTF/lab slash commands、CLI lab 状态行、OpenAI-compatible streaming chunk 合并、usage fallback 和中文友好的确认优先 system prompt sections 都已经接上；普通 CLI 已改为复古终端风格彩色分层 WEAVER FIELD OPS 启动 banner、彩色 slash command 导航、无标题用户消息块、底部 token/context 状态行和输入分隔线，蓝紫主要用于 Markdown 与少量强调。

## 这次已经完成的事

- 新增 `src/weaver_py/security/` 模块：SecurityContext、EvidenceStore、build_writeup
- 新增 CTF/lab slash commands：`/target`、`/note`、`/evidence`、`/writeup`
- session report 现在包含 target、phase、evidence、next action
- CLI 运行状态行显示 lab context（phase、evidence count、target）
- OpenAI-compatible `_merge_chat_chunks()` 增强：按 index 排序输出、缺省 `call_{index}` id、type 合并和 reasoning_content replay
- OpenAI-compatible streaming 请求会带 `stream_options.include_usage`，遇到 400/422 自动去掉该字段重试；网关不返回 usage 时用 prompt/messages 和回复文本做保守 token 估算
- 修复 session phase/confidence 状态分裂（统一从 SecurityContext 回写）
- 修复 `/target`、`/note` 大小写不敏感参数解析
- 清理了测试 demo 和临时运行产物，删除旧 TypeScript/Bun 运行线相关文件
- 增加了复古彩色分层 WEAVER FIELD OPS banner、彩色 slash command 导航、CLI Rich Markdown theme，并把整体界面收回到克制终端配色
- 调整了 CLI transcript：交互输入不二次回显，工具点表示待执行/成功/失败状态，交互终端里工具行原地更新，运行中动态计时、结束后显示总耗时
- 修复了用户 prompt 块的中文宽字符对齐问题，改用 Rich cell-width helper 裁剪/补齐；底部状态行会显示 ctx、phase、evidence 数和 target，并转义 phase/target 中的 Rich markup 字符
- 每轮输出后用当前 phase/target/evidence/token 状态打印底部状态行；交互回车后会清掉原始输入行和上一轮底部状态，只保留上推后的无标题用户消息块；非空 prompt 会在 selector 和 `/mcp reload` 特殊处理决策后统一渲染，slash command 不再跳过该视觉流；同时防御性剥离输入开头 UTF-8 BOM，兼容 PowerShell/管道输入
- smoke 测试覆盖 CTF/lab、安全上下文、PowerShell、retro palette/banner/helpers、CLI exit prompt block 和 chat usage fallback
- 同步了根目录接续文档到当前真实状态
- system prompt 从英文 monolithic prompt 改为中文友好的 section 体系，覆盖身份、授权/scope/影响确认、渗透测试工作流、工具调用、evidence/writeup、phase tracking 和输出风格

## 当前配置约定

- `.weaver/settings.json`：Weaver 自身配置
- `.mcp.json`：项目或第三方 MCP
- `.weaver/skills/`：项目技能
- `CLAUDE.md`：接续索引和工作约定

## 下次继续的优先级

1. 继续稳定 OpenAI-compatible streaming / tool_calls 主路径（真实网关端到端验证）
2. 完善 CTF/lab 最小闭环体验（scope 提示、evidence 记录引导、writeup 增强）
3. 权限确认策略，让 prompt 的确认优先语言和工具执行策略保持一致
4. 后续再考虑 prompt cache、override/append layer、agent-specific prompt layer

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
