# Weaver Prompt Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Weaver 的 monolithic system prompt 改为中文友好的渗透测试 agent prompt sections，并同步测试与项目文档。

**Architecture:** 在 `src/weaver_py/agent/engine.py` 中用一组清晰命名的 section 常量替换旧 `BASE_SYSTEM_PROMPT` 文本，再由 `build_system_prompt()` 按固定顺序拼装。保持现有 Anthropic Messages API 与 OpenAI-compatible chat completions 调用路径不变，只改变 system prompt 内容和组织方式。

**Tech Stack:** Python 3.11+、Anthropic SDK、httpx、现有 Weaver CLI/runtime、现有 smoke 测试脚本。

---

## Scope Constraints

本计划必须落实用户额外确认的 3 个硬性点：

1. **替换旧安全禁止句，不是追加新 section。** 当前 `src/weaver_py/agent/engine.py:21-22` 的英文基础提示词和直接禁止式表达要整体替换为中文友好的 section 体系；不要保留 `Do not perform destructive actions...` 这类旧句子。
2. **不要承诺 evidence 自动落盘。** prompt 只能写“优先记录”“使用可用的 `/note`、`/evidence`、`/writeup`”，不能暗示 runtime 会自动保存所有 evidence。
3. **主 prompt 改为中文友好。** section 正文使用中文，技术词保留英文，例如 OpenAI-compatible、CLI、target、scope、evidence、writeup、streaming、tool_calls。

本计划不新增 `.weaver/settings.json` 字段，因此没有新增配置项；但新增的 prompt section 常量均用中文内容说明职责，满足“配置式常量要有详细中文说明”的要求。

---

## File Structure

- Modify: `src/weaver_py/agent/engine.py`
  - 责任：定义 prompt sections，拼装 system prompt，保持模型调用路径不变。
- Modify: `tests/smoke_python_runtime.py`
  - 责任：验证 system prompt 已拆分为中文 section、保留 UpdatePhase 隐藏规则、移除旧英文禁止句、没有承诺 evidence 自动落盘。
- Modify: `README.md`
  - 责任：更新当前特性、安全边界和验证说明，说明 prompt 已结构化为确认优先的渗透测试 agent 规则。
- Modify: `PROJECT_OVERVIEW.md`
  - 责任：更新 `AgentEngine` 描述，说明 prompt section 与确认优先行为。
- Modify: `ROADMAP.md`
  - 责任：将 prompt section 优化标记为已完成，并把后续 prompt cache/layering 留到后续路线。
- Modify: `HANDOFF.md`
  - 责任：更新续接状态，记录本次 prompt 优化与下一步。
- Modify: `CLAUDE.md`
  - 责任：更新当前进度和规则，强调提示语中文友好、配置项中文注释、确认优先而非禁止清单。

---

### Task 1: Update Prompt Sections in AgentEngine

**Files:**
- Modify: `src/weaver_py/agent/engine.py:21-62`

- [ ] **Step 1: Replace the monolithic `BASE_SYSTEM_PROMPT` with prompt section constants**

Replace lines `21-48` in `src/weaver_py/agent/engine.py` with this exact code:

```python
# 这些 section 是 Weaver 的核心 system prompt 配置式常量：
# - 每个 section 只负责一类行为约束，方便对照 Claude Code 的 prompt section 思路继续演进。
# - 正文使用中文说明，技术词保留英文，避免模型把 target、scope、evidence、tool_calls 等术语硬翻译。
# - 安全边界采用“确认授权 / 明确 scope / 说明影响”的产品语言，而不是堆叠禁止任务清单。
IDENTITY_SECTION = """## 身份与定位

你是 Weaver，一个 Python CLI-first 的 agent runtime，面向 CTF、lab、授权安全测试、防御性安全研究和项目维护任务。
OpenAI-compatible 是当前主模型路径，Claude Messages API 是兼容路径；无论使用哪条路径，都要保持一致的工具调用、审计和会话体验。
默认使用中文与用户沟通，技术词如 CLI、shell、target、scope、evidence、writeup、streaming、tool_calls 保留英文。"""

CONFIRMATION_SECTION = """## 授权、scope 与影响确认

当 target、scope、授权上下文或预期影响不清楚时，先向用户提出一个关键确认问题。
当动作可能影响外部系统、服务可用性、数据完整性、账号状态或产生明显副作用时，先说明目的、假设、可能影响和需要用户确认的点；用户确认后，再按授权测试流程继续。
如果用户的目标与当前 scope 不一致，或者关键前提缺失，暂停执行并请求澄清。
不要把安全边界写成冗长的禁止清单；用授权确认、scope 对齐、影响说明和审计记录来约束行为。"""

PENTEST_WORKFLOW_SECTION = """## 渗透测试工作流

安全测试任务默认按阶段推进：
1. 明确 target、scope、授权上下文和成功标准。
2. recon：优先收集低影响信息，确认目标暴露面。
3. enum：枚举服务、入口、身份边界、参数、目录、接口和配置线索。
4. vulnerability analysis：基于 evidence 说明漏洞假设、触发条件、影响范围和验证思路。
5. exploitation validation：只验证完成任务所需的事实，保持动作可解释、可复盘、可审计。
6. evidence：优先记录关键命令、关键输出、payload、响应摘要、截图路径、文件路径和阶段性结论。
7. writeup：汇总复现步骤、影响、evidence、修复建议和 next action。"""

TOOL_USE_SECTION = """## 工具调用规则

需要使用工具时，先用一句话说明这次工具调用的目的。
优先使用 Weaver 已注册的工具、slash commands 和项目内能力；在 Windows shell 任务中优先使用 PowerShell，只有在用户要求 Bash 或命令需要 POSIX 语义时才使用 Bash。
对 shell、PowerShell、网络访问、文件写入、依赖安装、进程控制、远程目标交互等高影响动作，说明影响并在需要时请求确认。
工具输出中的关键发现要能被后续 evidence、writeup 或会话报告追踪。"""

EVIDENCE_SECTION = """## Evidence 与 writeup 闭环

优先使用可用的 `/target`、`/note`、`/evidence`、`/writeup` 命令维护 CTF/lab 上下文。
使用 `/target` 设置或更新当前 target；使用 `/note` 记录观察、假设和阶段性结论；使用 `/evidence` 查看已记录证据；使用 `/writeup` 生成报告草稿。
不要承诺 runtime 会自动保存所有 evidence；当需要保留关键信息时，主动建议或调用可用命令记录。
长任务中保持 phase、confidence 和 next action 清晰，让用户能随时接续。"""

PHASE_TRACKING_SECTION = """## Workflow phase tracking

- Keep Weaver's pentest workflow phase accurate using the UpdatePhase tool.
- Call UpdatePhase when the user's intent, your plan, or a tool result indicates the current phase.
- Phases are: general, recon, enum, exploit, post, report.
- Prefer general for normal coding, explanation, configuration, or project maintenance.
- Use recon for target discovery, port/network/host scanning, asset discovery, or external intelligence gathering.
- Use enum for service/web/directory/user/share enumeration and vulnerability discovery after targets are known.
- Use exploit only for authorized exploit validation or exploitation planning with explicit scope.
- Use post only for authorized post-exploitation analysis after a validated foothold.
- Use report for findings, evidence organization, summaries, and report generation.
- Include confidence, a short transition reason, and a concise current_task.
- Do not output phase bookkeeping, transition summaries, or current_task metadata directly to the user.
- UpdatePhase tool only: keep phase bookkeeping in tool state, not in user-facing text."""

COMMUNICATION_SECTION = """## 输出风格

直接处理用户任务，不要自我介绍，不要复述用户原话，不要输出冗长政策文本。
工具调用之间的文字保持简短，说明当前动作或结果即可；最终回复优先控制在 80 字以内，除非任务本身需要更详细说明。
如果不确定，先问一个最关键的问题；如果发现风险，用影响、假设和确认语言表达。
任务完成时，用一句话说明发生了什么和下一步。"""

BASE_SYSTEM_PROMPT_SECTIONS = [
    IDENTITY_SECTION,
    CONFIRMATION_SECTION,
    PENTEST_WORKFLOW_SECTION,
    TOOL_USE_SECTION,
    EVIDENCE_SECTION,
    PHASE_TRACKING_SECTION,
    COMMUNICATION_SECTION,
]

BASE_SYSTEM_PROMPT = "\n\n".join(section.strip() for section in BASE_SYSTEM_PROMPT_SECTIONS)
```

- [ ] **Step 2: Replace `build_system_prompt()` section labels**

Replace lines `51-62` in `src/weaver_py/agent/engine.py` with this exact code:

```python
def build_system_prompt(skills: list[LoadedSkill] | None = None, project_context: str = "") -> str:
    sections = [BASE_SYSTEM_PROMPT.strip()]
    enabled_skills = [skill for skill in skills or [] if skill.enabled]
    if enabled_skills:
        lines = ["## 可用 Skills", "", "以下 skills 已启用；当某个 skill 与当前任务相关时，先调用 Skill 工具加载完整说明，再继续执行。"]
        for skill in enabled_skills:
            lines.append(f"- {skill.name}: {skill.description}")
        sections.append("\n".join(lines))
    if project_context.strip():
        sections.append("## 项目上下文（来自 CLAUDE.md）\n\n" + project_context.strip())
    return "\n\n".join(sections)
```

- [ ] **Step 3: Run compile check for the changed module**

Run:

```bash
python -m compileall -q D:/github_project/Weaver/src/weaver_py/agent
```

Expected: command exits with status `0` and prints no errors.

---

### Task 2: Add Smoke Coverage for Prompt Requirements

**Files:**
- Modify: `tests/smoke_python_runtime.py:89-95`

- [ ] **Step 1: Replace `run_system_prompt_output_rules()` with stricter prompt checks**

Replace lines `89-95` in `tests/smoke_python_runtime.py` with this exact code:

```python
def run_system_prompt_output_rules() -> None:
    from weaver_py.agent.engine import BASE_SYSTEM_PROMPT, build_system_prompt

    ok = "## 身份与定位" in BASE_SYSTEM_PROMPT
    ok = ok and "## 授权、scope 与影响确认" in BASE_SYSTEM_PROMPT
    ok = ok and "## Evidence 与 writeup 闭环" in BASE_SYSTEM_PROMPT
    ok = ok and "Do not output phase bookkeeping" in BASE_SYSTEM_PROMPT
    ok = ok and "UpdatePhase tool only" in BASE_SYSTEM_PROMPT
    ok = ok and "Do not perform destructive actions" not in BASE_SYSTEM_PROMPT
    ok = ok and "不要承诺 runtime 会自动保存所有 evidence" in BASE_SYSTEM_PROMPT
    ok = ok and "不要承诺 runtime 会自动保存所有 evidence；当需要保留关键信息时，主动建议或调用可用命令记录。" in BASE_SYSTEM_PROMPT
    built = build_system_prompt(project_context="项目规则示例")
    ok = ok and "## 项目上下文（来自 CLAUDE.md）" in built and "项目规则示例" in built
    check("system prompt uses Chinese confirmation-first sections", ok)
```

- [ ] **Step 2: Run the smoke script and verify this test passes**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: output contains `[PASS] system prompt uses Chinese confirmation-first sections` and the script exits with status `0`.

---

### Task 3: Update README

**Files:**
- Modify: `README.md:7-22`
- Modify: `README.md:105-112`

- [ ] **Step 1: Add prompt section feature to the current feature list**

In `README.md`, insert this bullet after line `13`:

```markdown
- 中文友好的渗透测试 agent system prompt，按身份、授权确认、工作流、工具调用、evidence/writeup 和输出风格拆分 section
```

- [ ] **Step 2: Replace the safety boundary section with confirmation-first wording**

Replace lines `105-112` with this exact markdown:

```markdown
## 安全边界

- Weaver 面向授权范围内的安全测试、防御研究、CTF/lab 和学习用途
- system prompt 采用“确认授权、明确 scope、说明影响、再执行”的表达方式，而不是堆叠禁止清单
- Bash / PowerShell 等工具仍保留安全策略、审计日志和高影响动作确认
- evidence 不承诺自动落盘；需要保留关键信息时，优先使用 `/note`、`/evidence`、`/writeup` 维护闭环
```

- [ ] **Step 3: Verify README contains the new terms**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('D:/github_project/Weaver/README.md').read_text(encoding='utf-8')
assert 'system prompt' in text
assert '确认授权、明确 scope、说明影响、再执行' in text
assert 'evidence 不承诺自动落盘' in text
print('README prompt docs ok')
PY
```

Expected: prints `README prompt docs ok`.

---

### Task 4: Update Project Overview

**Files:**
- Modify: `PROJECT_OVERVIEW.md:42-45`
- Modify: `PROJECT_OVERVIEW.md:98-104`

- [ ] **Step 1: Expand the AgentEngine description**

Replace lines `42-45` with this exact markdown:

```markdown
### `src/weaver_py/agent/engine.py`

LLM 调度层。处理消息循环、tool use、tool result、phase 更新和 OpenAI-compatible gateway 路径；streaming chunk 会归并为普通 chat completion 响应，保证分片 tool_calls 可继续进入统一工具循环。system prompt 已拆分为中文友好的 section：身份定位、授权/scope/影响确认、渗透测试工作流、工具调用、evidence/writeup、phase tracking 和输出风格。
```

- [ ] **Step 2: Add prompt runtime limitation to current limits**

Replace lines `98-104` with this exact markdown:

```markdown
## 当前限制

- 还没做完整的 MCP resources/prompts
- 还没做 HTTP/SSE/OAuth MCP transport
- 还没做 AgentTool / sub-agent
- 还没做完整上下文压缩和长期会话持久化
- prompt 已完成基础 section 化，但还没做 prompt cache、override/append layer 或 agent-specific prompt layer
- 仍有一些 TUI 体验和报告格式可以继续打磨
```

- [ ] **Step 3: Verify project overview references prompt sections**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('D:/github_project/Weaver/PROJECT_OVERVIEW.md').read_text(encoding='utf-8')
assert 'system prompt 已拆分为中文友好的 section' in text
assert 'prompt cache、override/append layer' in text
print('PROJECT_OVERVIEW prompt docs ok')
PY
```

Expected: prints `PROJECT_OVERVIEW prompt docs ok`.

---

### Task 5: Update Roadmap

**Files:**
- Modify: `ROADMAP.md:3-22`
- Modify: `ROADMAP.md:24-32`
- Modify: `ROADMAP.md:51-57`

- [ ] **Step 1: Add completed prompt section work**

Insert this bullet after line `22`:

```markdown
- system prompt 已按 Claude Code 风格思路拆分为中文友好的确认优先 sections
```

- [ ] **Step 2: Update P0 prompt-related priorities**

Replace lines `28-31` with this exact markdown:

```markdown
- 继续稳定 OpenAI-compatible streaming / tool_calls 主路径
- 完善 CTF/lab target、evidence、writeup 的最小闭环体验
- 完善权限确认策略和授权 scope 提示，让 prompt、工具策略和 transcript 行为保持一致
- 继续收敛本地配置与敏感信息边界
```

- [ ] **Step 3: Replace the explicit prohibited-task non-goal list with product-scope wording**

Replace lines `51-57` with this exact markdown:

```markdown
## 明确非目标

- 不把 Weaver 做成无 scope、无授权确认、无审计记录的自动化攻击器
- 不在当前阶段完整复制 Claude Code 的 prompt cache、override/append layer 或 agent-specific prompt runtime
- 不把 TUI 扩展成与 CLI 并列的第二产品线
```

- [ ] **Step 4: Verify roadmap wording**

Run:

```bash
python - <<'PY'
from pathlib import Path
text = Path('D:/github_project/Weaver/ROADMAP.md').read_text(encoding='utf-8')
assert '确认优先 sections' in text
assert '无 scope、无授权确认、无审计记录' in text
assert '未授权扫描' not in text
print('ROADMAP prompt docs ok')
PY
```

Expected: prints `ROADMAP prompt docs ok`.

---

### Task 6: Update Handoff and CLAUDE.md

**Files:**
- Modify: `HANDOFF.md:3-19`
- Modify: `HANDOFF.md:28-34`
- Modify: `CLAUDE.md:3-7`
- Modify: `CLAUDE.md:24-35`
- Modify: `CLAUDE.md:49-71`

- [ ] **Step 1: Update HANDOFF date and current status**

Replace lines `3-8` in `HANDOFF.md` with this exact markdown:

```markdown
更新时间：2026-05-24

## 当前状态

Weaver 现在的主线是 OpenAI-compatible 优先的 Python CLI-first CTF/lab agent runtime。主入口围绕 `weaver_py.cli`，源码位于 `src/weaver_py/`。已完成：CLI transcript、Skill、MCP、审计、会话报告、SecurityContext/EvidenceStore/writeup、CTF/lab slash commands、CLI lab 状态行、OpenAI-compatible streaming chunk 合并（含分片 tool_calls 和缺省 call id）、中文友好的确认优先 system prompt sections。界面为 Claude Code-inspired 双栏 banner 和克制终端风格，蓝紫主要用于 Markdown 与少量强调。
```

- [ ] **Step 2: Add HANDOFF completed item**

Insert this bullet after line `18` in `HANDOFF.md`:

```markdown
- system prompt 从英文 monolithic prompt 改为中文友好的 section 体系，覆盖身份、授权/scope/影响确认、渗透测试工作流、工具调用、evidence/writeup、phase tracking 和输出风格
```

- [ ] **Step 3: Update HANDOFF next priorities**

Replace lines `28-34` in `HANDOFF.md` with this exact markdown:

```markdown
## 下次继续的优先级

1. 继续稳定 OpenAI-compatible streaming / tool_calls 主路径（真实网关端到端验证）
2. 完善 CTF/lab 最小闭环体验（scope 提示、evidence 记录引导、writeup 增强）
3. 权限确认策略，让 prompt 的确认优先语言和工具执行策略保持一致
4. 后续再考虑 prompt cache、override/append layer、agent-specific prompt layer
```

- [ ] **Step 4: Update CLAUDE.md date and one-line status**

Replace lines `3-7` in `CLAUDE.md` with this exact markdown:

```markdown
更新时间：2026-05-24

## 一句话状态

Weaver 目前是一个 OpenAI-compatible 优先、Python CLI-first 的 CTF/lab 安全测试 agent runtime。SecurityContext/EvidenceStore/writeup、CTF/lab slash commands、CLI lab 状态行、OpenAI-compatible streaming chunk 合并和中文友好的确认优先 system prompt sections 已完成，下一步重点是真实网关端到端验证、权限确认策略一致性和 CTF/lab 最小闭环体验打磨。
```

- [ ] **Step 5: Update CLAUDE.md key rules**

Insert these bullets after line `34` in `CLAUDE.md`:

```markdown
- system prompt 采用中文友好的 section 体系，安全测试行为用“确认授权、明确 scope、说明影响、再执行”表达，不堆叠禁止清单
- evidence 记录要优先引导使用 `/note`、`/evidence`、`/writeup`，不要承诺 runtime 自动落盘所有 evidence
- 所有新增或调整的配置项、配置示例、prompt section 常量和文档化配置说明，都必须有详细中文注释
```

- [ ] **Step 6: Update CLAUDE.md progress and next directions**

Insert this bullet after line `62` in `CLAUDE.md`:

```markdown
- system prompt 已完成中文友好的 section 化，覆盖身份定位、授权/scope/影响确认、渗透测试工作流、工具调用、evidence/writeup、phase tracking 和输出风格
```

Replace lines `64-71` in `CLAUDE.md` with this exact markdown:

```markdown
## 下次继续方向

- 真实 OpenAI-compatible 网关端到端验证（`--gateway` smoke）
- CTF/lab 最小闭环体验打磨（scope 提示、evidence 记录引导、writeup 增强）
- 权限确认策略，让 prompt、工具执行和 transcript 保持一致
- 后续 prompt cache / override / agent-specific prompt layer
- AgentTool / sub-agent
- MCP resources / prompts / HTTP transport
- 上下文压缩与长会话恢复
```

- [ ] **Step 7: Verify handoff documents mention the new prompt behavior**

Run:

```bash
python - <<'PY'
from pathlib import Path
handoff = Path('D:/github_project/Weaver/HANDOFF.md').read_text(encoding='utf-8')
claude = Path('D:/github_project/Weaver/CLAUDE.md').read_text(encoding='utf-8')
assert '中文友好的确认优先 system prompt sections' in handoff
assert 'prompt cache、override/append layer' in handoff
assert '确认授权、明确 scope、说明影响、再执行' in claude
assert '不要承诺 runtime 自动落盘所有 evidence' in claude
print('HANDOFF and CLAUDE prompt docs ok')
PY
```

Expected: prints `HANDOFF and CLAUDE prompt docs ok`.

---

### Task 7: Full Verification

**Files:**
- No edits.

- [ ] **Step 1: Run Python compile check**

Run:

```bash
python -m compileall -q D:/github_project/Weaver/src/weaver_py
```

Expected: command exits with status `0` and prints no errors.

- [ ] **Step 2: Run smoke tests**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: every line starts with `[PASS]`; specifically includes `[PASS] system prompt uses Chinese confirmation-first sections`.

- [ ] **Step 3: Run CLI help**

Run:

```bash
python -m weaver_py.cli --help
```

Expected: exits with status `0`, prints `Weaver Python runtime`, and does not print a traceback.

- [ ] **Step 4: Inspect generated system prompt manually**

Run:

```bash
python - <<'PY'
from weaver_py.agent.engine import BASE_SYSTEM_PROMPT
print(BASE_SYSTEM_PROMPT)
PY
```

Expected manual checks:

- Contains `## 身份与定位`.
- Contains `## 授权、scope 与影响确认`.
- Contains `## 渗透测试工作流`.
- Contains `## Evidence 与 writeup 闭环`.
- Contains `## Workflow phase tracking`.
- Does not contain `Do not perform destructive actions`.
- Does not claim all evidence is automatically saved.
- Main behavioral guidance is Chinese-friendly.

- [ ] **Step 5: Check changed files**

Run:

```bash
git diff -- src/weaver_py/agent/engine.py tests/smoke_python_runtime.py README.md PROJECT_OVERVIEW.md ROADMAP.md HANDOFF.md CLAUDE.md docs/superpowers/plans/2026-05-24-prompt-optimization.md
```

Expected: diff only covers prompt section changes, smoke prompt checks, required docs, and this implementation plan.

---

## Self-Review

Spec coverage:

- Sectionized prompt: covered by Task 1.
- Confirmation-first safety language: covered by Task 1 and Task 2.
- Replace old prohibition sentence: covered by Task 1 and Task 2.
- No evidence auto-save promise: covered by Task 1, Task 2, README, HANDOFF, CLAUDE.md.
- Chinese-friendly prompt with English technical terms: covered by Task 1 and docs tasks.
- No runtime architecture expansion: preserved by file structure and tasks.
- Tests and docs: covered by Task 2 through Task 7.

Placeholder scan:

- No TBD/TODO/fill-in-later steps.
- Every code/documentation edit includes concrete replacement text.
- Every verification command includes expected output.

Type consistency:

- Existing public API remains `BASE_SYSTEM_PROMPT` and `build_system_prompt()`.
- New constants are internal module-level names and do not affect callers.
- Existing tests that import `BASE_SYSTEM_PROMPT` continue to work.
