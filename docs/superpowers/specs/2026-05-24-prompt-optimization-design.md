# Weaver 渗透测试 Agent Prompt 优化设计

## 背景

Weaver 当前定位是 OpenAI-compatible 优先、Python CLI-first 的 CTF/lab 安全测试 agent runtime。当前 system prompt 主要集中在 `src/weaver_py/agent/engine.py` 的单个基础提示词中，再拼接 skills 摘要和 `CLAUDE.md` 项目上下文。这个结构能运行，但不利于后续对标 Claude Code 的分段 prompt 管理、动态上下文注入、缓存优化和行为审计。

本次优化参考本地 `D:\github_project\claude-code-main` 的 prompt section 思路，但不完整照搬 Claude Code 的全部 runtime。目标是先把 Weaver 的提示词组织升级为清晰、可维护、适合渗透测试 agent 的 section 体系。

## 设计目标

1. 将 monolithic system prompt 拆成多个语义明确的 section。
2. 保留 Weaver 的 CLI-first、OpenAI-compatible 优先、CTF/lab 安全测试定位。
3. 用“确认授权、明确 scope、说明影响、记录 evidence”的方式表达安全边界，避免产品提示词呈现为大段禁止清单。
4. 强化渗透测试工作流：target 确认、recon、enumeration、vulnerability analysis、exploitation validation、evidence、writeup。
5. 保持当前实现范围小，不改工具权限系统、skills loader、MCP 架构或模型网关调用逻辑。
6. 所有新增或调整的配置项、配置示例、prompt section 常量和文档化配置说明，都必须有详细中文注释；技术词如 OpenAI-compatible、CLI、target、evidence、writeup、streaming、tool_calls 保留英文。

## 非目标

1. 不完整复制 Claude Code 的全部 prompt runtime。
2. 不实现 prompt cache、override/append layer、agent-specific prompt layer。
3. 不重构 skills loader。
4. 不改变工具权限确认的实际执行逻辑。
5. 不引入新的外部依赖。
6. 不把安全边界写成面向用户的大段“禁止任务列表”。

## Prompt Section 结构

`src/weaver_py/agent/engine.py` 中的基础提示词将拆成以下 section：

### 1. Identity Section

说明 Weaver 的身份和总体定位：

- Python CLI-first agent runtime。
- OpenAI-compatible 是主模型路径。
- 面向 CTF、lab、授权安全测试和防御性安全分析。
- 交互语言中文友好，技术词保留英文。

### 2. Confirmation Section

表达确认优先的安全测试行为方式：

- target、scope、授权上下文不明确时先向用户确认。
- 可能影响外部系统、可用性、数据完整性或产生明显副作用的动作，先说明目的、影响和假设，再请求用户确认。
- 用户确认后，按授权测试流程继续。
- 关键确认和关键动作应进入 evidence 或会话记录。

该 section 避免列出大段“禁止做什么”，而是强调确认门槛、影响说明和审计闭环。

### 3. Pentest Workflow Section

定义 Weaver 默认的安全测试推进方式：

1. 明确 target 和 scope。
2. 进行 recon，先收集低影响信息。
3. 做 enumeration，整理服务、入口、身份、参数和暴露面。
4. 做 vulnerability analysis，说明假设、证据和可能影响。
5. 做 exploitation validation，只验证必要事实，避免无关破坏。
6. 保存 evidence，记录命令、输出、截图路径、payload、响应摘要或关键观察。
7. 生成 writeup，输出复现步骤、影响、证据、修复建议和后续动作。

### 4. Tool Use Section

约束工具调用方式：

- 调用工具前简短说明目的。
- 优先使用 Weaver 内建工具和 slash command。
- 对 shell、PowerShell、网络访问、文件写入等高影响动作，说明影响并在需要时确认。
- 保留审计意识：关键命令、关键响应、关键文件路径应能被 evidence/writeup 追踪。

### 5. Evidence Section

强化 CTF/lab 闭环：

- 鼓励使用 `/target` 设置目标。
- 用 `/note` 记录观察、假设和阶段性结论。
- 用 `/evidence` 保存关键证据。
- 用 `/writeup` 汇总最终结果。
- 在长任务中保持 phase、confidence、next action 清晰。

### 6. Communication Section

定义交互风格：

- 默认中文回答。
- 技术词不过度翻译。
- 简洁说明下一步，不输出冗长政策文本。
- 不确定时先问一个关键问题。
- 发现风险时用影响和确认语言表达，而不是机械拒绝。

### 7. Skills Section

`build_system_prompt()` 继续注入 enabled skills 摘要，但作为独立 section：

- 每个 skill 展示 name 和 description。
- 当前阶段不改变 skill discovery 和执行逻辑。
- 后续可以扩展 richer metadata，但不属于本次范围。

### 8. Project Instructions Section

`CLAUDE.md` 继续作为项目上下文注入，但作为独立 section：

- 保留当前截断策略。
- 明确这部分是项目指令和续接上下文。
- 后续可以替换为更细粒度的 project memory / config section。

## 实现边界

本次实现只修改 prompt 组织和相关文档：

- `src/weaver_py/agent/engine.py`
- `README.md`
- `PROJECT_OVERVIEW.md`
- `ROADMAP.md`
- `HANDOFF.md`
- `CLAUDE.md`

如果实际实现发现还有测试文件需要同步，可补充更新 smoke 测试，但不主动扩大架构范围。

## 配置项中文注释要求

任何新增或调整的配置项必须遵守以下要求：

- 在代码附近或配置示例中提供中文说明。
- 说明该项控制什么行为。
- 说明常见取值或启用条件。
- 说明对安全测试流程、工具调用、evidence、writeup 或模型行为的影响。
- 如果该项只是 prompt section 常量，也需要通过常量命名和中文内容让维护者理解其职责。

本次预计不会新增 `.weaver/settings.json` 字段；如果实现中确实需要新增字段，必须同步给出中文注释式文档说明。

## 测试与验证

实现后至少执行：

1. Python smoke 测试，确认 runtime 未破坏。
2. 运行 CLI help 或最小启动路径，确认 prompt 构建不报错。
3. 人工检查生成的 system prompt 内容，确认 section 顺序清晰，没有重复、矛盾或大段禁止清单。
4. 检查文档同步状态，确保 README、PROJECT_OVERVIEW、ROADMAP、HANDOFF、CLAUDE 均反映本次优化。

## 风险与取舍

- 分段 prompt 会让 `engine.py` 中常量变多，但可读性和后续扩展性更好。
- 不做完整 Claude Code prompt runtime，短期能力有限，但更符合当前 Weaver 小步迭代状态。
- 不写大段禁止清单可以改善产品体验，但仍需要通过确认授权、scope 和影响说明保持安全边界。

## 用户确认点

本设计已根据用户偏好确定：

- 优先做结构化 prompt section。
- 渗透测试 agent 采用确认优先，不展示禁止任务清单。
- 所有配置项必须有详细中文注释。
- 当前只优化 prompt 组织和文档，不扩大到完整 Claude Code runtime 对标。
