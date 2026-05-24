# Weaver CTF/lab 渗透测试 Agent 设计规格

日期：2026-05-22

## 1. 设计目标

Weaver 的新主线定位为：

```text
OpenAI-compatible 优先的 CTF/lab 渗透测试 agent，
拥有接近 Claude Code 的终端交互体验，
但工作流、状态展示和报告能力专门服务安全测试学习与靶场场景。
```

这意味着 Weaver 不是普通 Claude Code 换皮，也不是企业级全自动 pentest 平台。第一阶段要做出一个适合 CTF、靶场、lab、授权学习环境的安全测试工作台：用户能设置 target，让 agent 帮助推进 recon、enum、exploit 验证和 report/writeup，并且终端体验足够流畅、美观、低干扰。

核心关键词：

- OpenAI-compatible 优先
- CTF/lab 优先
- Claude Code-like 终端体验
- 安全实验室风格 UI
- 证据驱动 workflow
- 中文友好提示语
- 关键代码路径保留详细中文注释

## 2. 非目标

P0 不追求以下内容：

- 不以 Claude 官方模型作为第一优先模型路径
- 不做企业级全自动渗透测试平台
- 不做未授权扫描、DoS、检测规避、凭证滥用或破坏性自动化
- 不做花哨黑客终端、霓虹绿大屏、过度动画或满屏装饰
- 不急于实现 AgentTool / sub-agent
- 不急于实现完整 MCP resources/prompts 或 HTTP/SSE/OAuth MCP transport
- 不急于实现长期会话恢复和完整上下文压缩

## 3. 产品定位

Weaver 应该呈现为一个安全实验室工作台：

```text
Claude Code 的顺滑工具调用体验
+
CTF/lab 的 target、phase、evidence、next action、writeup
+
OpenAI-compatible 模型网关优先
```

目标用户主要是：

- CTF 选手
- 靶场/lab 学习者
- 授权安全测试学习者
- 想研究 agent 架构和 Claude Code 风格 runtime 的开发者

因此，Weaver 的终端界面和提示语应该以中文友好为主，但常见技术词不硬翻译，例如：

- Bash
- shell
- CLI / TUI
- MCP
- OpenAI-compatible
- streaming
- tool_calls
- base_url
- model
- token
- writeup

这些词可以直接保留英文，必要时用中英混合表达。

## 4. P0 成功标准

P0 完成后，用户应该可以完成以下最小闭环：

1. 配置 OpenAI-compatible `base_url`、`model`、`api_key`。
2. 启动 Weaver CLI。
3. 使用 `/target` 设置当前 CTF/lab target。
4. 让 Weaver 根据题目或 target 辅助分析。
5. Weaver 能展示当前 phase、target、evidence 数量和下一步建议。
6. 用户能通过 `/note` 添加题目笔记。
7. 用户能通过 `/evidence` 查看证据列表。
8. 用户能通过 `/writeup` 生成 CTF/lab 风格 Markdown 草稿。
9. OpenAI-compatible 模型路径能稳定完成 streaming、tool_calls、tool result 续轮。
10. CLI transcript 保持接近 Claude Code 的流畅感，同时具备 Weaver 自己的安全实验室气质。

## 5. 总体架构

当前架构可概括为：

```text
CLI / TUI
  -> WeaverSession
  -> AgentEngine
  -> ToolRegistry
  -> SkillLoader
  -> McpManager
  -> Report / Audit
```

P0 后建议调整为：

```text
CLI / TUI
  -> WeaverSession
      -> AgentEngine
      -> SecurityContext
      -> EvidenceStore
      -> ToolRegistry
      -> SkillLoader
      -> McpManager
      -> Report / Writeup / Audit
```

新增或强化的核心概念：

- `SecurityContext`：当前安全任务状态
- `EvidenceStore`：当前 session 的证据和笔记
- `WriteupBuilder`：把状态、证据、对话摘要整理成 CTF/lab writeup

推荐新增目录：

```text
src/weaver_py/security/
  __init__.py
  context.py
  evidence.py
  writeup.py
```

如果实现时发现新增目录成本过高，也可以先放在 `runtime/` 下，但长期更推荐独立 `security/` 层，避免 session、command、UI 逻辑混在一起。

## 6. 模型调用策略

模型路径优先级调整为：

```text
P0：OpenAI-compatible chat completions
P1：更强 provider 兼容和错误诊断
P2：Claude Messages API 原生 streaming 完善
```

当前判断逻辑可以继续保留：

```text
claude-* 模型      -> Anthropic Messages API
非 claude-* 模型   -> OpenAI-compatible chat completions
```

但产品主线要明确：OpenAI-compatible 是第一优先路径。

P0 重点增强：

- `/v1/chat/completions` streaming
- `delta.content` 实时输出
- `delta.tool_calls` 累积与合并
- function arguments JSON 解析
- tool result 回填并继续下一轮模型调用
- `usage` 缺失时不报错
- base_url、api_key、model、tools 不兼容时给出中文友好的错误提示
- `custom_headers` 继续支持，但避免泄露敏感值

需要兼容的常见网关差异：

- 有些网关不返回 `usage`
- 有些网关不完整支持 streaming tool_calls
- 有些网关 function arguments 会分片返回
- 有些网关错误信息不标准
- 有些网关对 system role、tools schema 支持不完全

实现时应在关键解析逻辑处写中文注释，说明为什么要这样兼容，而不是只写一段难懂的合并逻辑。

## 7. 安全任务状态模型

P0 的状态模型保持内存态，不引入数据库。

建议结构：

```text
SecurityContext:
  mode
  target
  challenge
  phase
  current_task
  next_action
```

字段含义：

- `mode`：默认 `ctf_lab`，后续可扩展为 `authorized_pentest` 或 `general`
- `target`：当前题目、URL、host、文件或靶场目标
- `challenge`：当前题目名，可选
- `phase`：当前阶段，沿用 `general / recon / enum / exploit / post / report`
- `current_task`：当前正在推进的任务
- `next_action`：建议的下一步动作

证据结构：

```text
EvidenceItem:
  kind
  title
  source
  summary
  phase
  created_at
```

字段含义：

- `kind`：`file`、`url`、`command`、`finding`、`note` 等
- `title`：证据标题，例如 `/admin exposed`
- `source`：来源，例如命令、文件路径、URL
- `summary`：中文摘要
- `phase`：发现该证据时的阶段
- `created_at`：创建时间

P0 可把 note 也作为 evidence 的一种 `kind=note` 处理，减少概念数量。

## 8. Slash commands 设计

保留现有命令：

```text
/status
/clear
/report
/tools
/skills
/mcp
/permissions
/init
/help
/exit
```

P0 新增命令：

```text
/target <value>
/note <text>
/evidence
/writeup
```

### 8.1 `/target <value>`

设置当前 target。

示例：

```text
/target http://web-lab.local
```

中文提示：

```text
Target 已设置：http://web-lab.local
```

技术词 `Target` 可以保留英文，因为安全测试语境中更自然。

### 8.2 `/note <text>`

添加当前题目笔记。

示例：

```text
/note 登录页返回 debug header，可能能泄露源码路径
```

输出：

```text
已添加 note：登录页返回 debug header，可能能泄露源码路径
```

### 8.3 `/evidence`

显示当前证据列表。

示例输出：

```text
Evidence:
  1. /admin exposed — enum
     来源：Bash(ffuf ...)
     摘要：目录枚举发现 /admin，可能存在后台入口。

  2. debug route leaks source — enum
     来源：http://web-lab.local/debug
     摘要：debug route 返回源码片段。
```

### 8.4 `/writeup`

生成 CTF/lab 风格 Markdown 草稿。

结构：

```markdown
# Challenge

# Target

# Summary

# Steps

# Evidence

# Solution

# Flag / Result

# Lessons Learned
```

P0 只输出 Markdown，不做 docx/html。

## 9. CLI / TUI 视觉与交互方向

所有 UI/CLI/TUI 相关实现前，需要调用相关 UI/design skills，例如 `frontend-design:frontend-design`，再进入具体实现。

视觉方向：

```text
安全实验室风格
冷静、清晰、专业
接近 Claude Code 的低干扰 transcript
```

避免：

- 大面积紫色
- 霓虹绿黑客风
- 满屏边框
- 满屏动画
- banner 过度装饰
- 输入重复回显
- 工具输出刷屏

推荐状态行：

```text
  ⎿ Lab ctf/lab · Phase enum · Evidence 3 · Target web-lab.local
```

推荐工具 transcript：

```text
○ Bash(ffuf ...)
● Bash(ffuf ...) · found 8 paths
● Read(app.py) · 120 lines
● Evidence(/admin) · added
```

推荐 assistant 总结：

```text
  ⎿ 判断：当前处于 enum 阶段
  ⎿ 关键证据：/admin 暴露，debug route 可疑
  ⎿ 下一步：检查 debug route 是否泄露源码或环境变量
```

UI 实现原则：

- 启动时可以显示完整 Weaver banner
- 每轮交互中只显示轻量状态，不重复大块 banner
- 运行中保留低频耗时和工具状态
- 工具完成后保留简洁的一行结果
- 长输出默认摘要，必要时再展示预览
- Markdown 渲染可以继续使用蓝紫强调，但整体 UI 不大面积紫色化

## 10. 权限和安全边界

P0 面向 CTF/lab，因此低风险学习场景应尽量顺滑，但边界必须保留。

低摩擦或允许：

- 本地题目文件读取
- 本地分析脚本
- 对明确 target 的普通 HTTP 请求
- 对明确 target 的低风险枚举
- CTF/lab 常见工具调用

需要确认：

- 多 host 扫描
- 长时间运行任务
- exploit 验证
- 写入敏感路径
- 可能影响外部系统的操作

拒绝：

- DoS
- 未授权公网大范围扫描
- 凭证滥用
- 检测规避
- 破坏性自动化

用户提示语应中文友好，例如：

```text
这个操作看起来会扫描多个 host。请确认这些目标都在你的授权范围或 CTF/lab 环境内。
```

不要把 `host`、`CTF/lab` 这类词硬翻译成不自然的中文。

## 11. Report 与 Writeup 区分

`/report` 保持当前语义：保存 Weaver session 报告，偏运行记录。

`/writeup` 用于 CTF/lab 解题报告，偏题目总结。

区别：

```text
/report  = session transcript / audit / runtime summary
/writeup = challenge solution / evidence / steps / result
```

P0 应避免混淆这两个命令。

## 12. 代码注释与中文文案规范

用户明确要求实现时写详细中文注释，因此 P0 实现时应遵守：

- 对模型 streaming 解析、tool_calls 合并、phase 更新、evidence 记录、writeup 生成等关键流程写中文注释
- 注释解释“为什么这么做”，尤其是兼容网关差异、安全边界、UI 状态流转
- 不需要给每一行都写注释，避免噪音
- 用户可见提示语使用自然中文
- 技术词保留英文或中英混用，不硬翻译

推荐注释风格：

```python
# OpenAI-compatible 网关经常把 tool_calls.arguments 分片返回，
# 这里按 index 累积，等 finish_reason 到来后再统一解析 JSON。
```

不推荐：

```python
# 工具调用参数字符串追加到临时字典
```

前者说明原因，后者只是重复代码行为。

## 13. 文档同步要求

完成用户可见修改后同步：

```text
README.md
PROJECT_OVERVIEW.md
ROADMAP.md
HANDOFF.md
CLAUDE.md
```

需要更新的重点：

- OpenAI-compatible 优先
- CTF/lab 优先
- Claude API 是兼容路径，不是 P0 主线
- 安全实验室 CLI/TUI 风格
- 新增 `/target`、`/note`、`/evidence`、`/writeup`
- 新增 `SecurityContext`、`EvidenceStore`、`WriteupBuilder`
- 中文注释和中文友好提示语规范

## 14. 验证标准

P0 验证至少包括：

```bash
python -m compileall -q D:/github_project/Weaver/src/weaver_py
python D:/github_project/Weaver/tests/smoke_python_runtime.py
python -m weaver_py.cli --help
```

新增功能后应增加 smoke 覆盖：

- `/target` 能设置 target
- `/note` 能添加 note
- `/evidence` 能显示 evidence
- `/writeup` 能生成 Markdown 草稿
- `/status` 能显示安全任务状态

UI 修改后必须实际启动 CLI 查看效果，不能只依赖测试。

## 15. 推荐实施顺序

P0 建议按以下顺序实现：

1. 新增 `SecurityContext`、`EvidenceItem`、`EvidenceStore`、`WriteupBuilder`。
2. `WeaverSession` 接入 security state。
3. 新增 `/target`、`/note`、`/evidence`、`/writeup`。
4. `/status` 接入 target、phase、evidence、next_action。
5. CLI 状态行显示 lab、phase、evidence、target。
6. 工具 transcript 预留 Evidence 事件展示能力。
7. 补强 OpenAI-compatible streaming tool_calls。
8. 增加 smoke 测试。
9. 更新根目录文档。
10. 实际运行 CLI 检查 UI。

## 16. 风险与取舍

### 16.1 过早做重型 AgentTool 的风险

AgentTool / sub-agent 很有价值，但 P0 如果先做它，容易拖慢核心体验闭环。第一阶段应先做 target、evidence、writeup、OpenAI-compatible 主路径和 CLI 体验。

### 16.2 UI 过度设计的风险

Weaver 需要安全实验室气质，但不能变成花哨黑客终端。实现时要用 UI/design skill 辅助判断视觉层级，但最终仍以低干扰、长时间可用为标准。

### 16.3 OpenAI-compatible 网关差异

不同网关对 tools、streaming、usage 的支持差异大。P0 应优先做到稳健和错误提示清楚，而不是假设所有网关完全兼容 OpenAI 官方行为。

### 16.4 中文注释过多的风险

用户需要详细中文注释帮助学习，但注释应集中在关键流程和非显然设计上，不要把简单代码逐行翻译成中文。

## 17. 最终结论

Weaver 的路线应从“Python Claude Code 风格 runtime”明确升级为：

```text
OpenAI-compatible 优先的 CTF/lab 安全测试 agent runtime。
```

P0 的核心不是堆功能，而是建立辨识度：

```text
模型主路径稳定
+
安全任务状态明确
+
evidence/writeup 最小闭环
+
安全实验室风格 CLI
```

这版设计通过后，下一步应进入 implementation plan，把上述内容拆成可执行的文件级任务。