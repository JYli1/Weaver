# Weaver CTF/lab Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Weaver's P0 CTF/lab security-task loop: OpenAI-compatible-first positioning, in-memory target/evidence/writeup state, friendly Chinese slash commands, and a restrained security-lab CLI status surface.

**Architecture:** Add a focused `weaver_py.security` package for task state, evidence, and writeup generation; wire it into `WeaverSession`, slash commands, reports, CLI status rendering, and smoke tests. Keep `AgentEngine` responsible for model/tool loop only, and improve OpenAI-compatible streaming/tool_calls robustness without turning provider support into a large abstraction.

**Tech Stack:** Python 3.11+, dataclasses, Rich CLI rendering, existing Weaver smoke test script, Anthropic SDK for Claude compatibility, httpx for OpenAI-compatible streaming.

---

## File Structure

Create:

- `src/weaver_py/security/__init__.py` — exports the small security-task API.
- `src/weaver_py/security/context.py` — owns current lab mode, target, challenge, phase, task, and next action.
- `src/weaver_py/security/evidence.py` — owns evidence/note dataclasses and in-memory evidence store rendering.
- `src/weaver_py/security/writeup.py` — builds a Markdown CTF/lab writeup from session state.

Modify:

- `src/weaver_py/runtime/session.py` — attach `SecurityContext` and `EvidenceStore`; keep them in sync with phase events; clear them on `/clear`; expose status fields.
- `src/weaver_py/runtime/commands.py` — add `/target`, `/note`, `/evidence`, `/writeup`; update `/status` and `/help` output through the existing command table.
- `src/weaver_py/runtime/report.py` — include target/phase/evidence summary in session reports.
- `src/weaver_py/cli.py` — render lab context in the dynamic status line without making the UI noisy.
- `src/weaver_py/agent/engine.py` — make OpenAI-compatible streaming/tool_calls parsing more robust; add Chinese comments at the non-obvious compatibility points.
- `src/weaver_py/ui/transcript.py` — optionally recognize an `Evidence` event if later emitted; keep current tool transcript compact.
- `tests/smoke_python_runtime.py` — add smoke checks for security state, commands, writeup, report integration, and OpenAI-compatible chunk merging.
- `README.md`, `PROJECT_OVERVIEW.md`, `ROADMAP.md`, `HANDOFF.md`, `CLAUDE.md` — document the revised product direction and new commands after code is working.

Execution note: Do not create git commits unless the user explicitly asks. The steps below include checkpoint boundaries; if the user later authorizes commits, commit only the files listed in each checkpoint.

---

## Task 1: Add security state tests first

**Files:**

- Modify: `tests/smoke_python_runtime.py`
- Later implementation files: `src/weaver_py/security/*.py`

- [ ] **Step 1: Add failing smoke checks for security context, evidence, and writeup**

Add these imports near the existing imports after `from weaver_py.runtime import WeaverSession, build_default_registry, handle_command`:

```python
from weaver_py.security import EvidenceStore, SecurityContext, build_writeup
```

Add this function after `run_transcript_renderer()`:

```python
def run_security_state() -> None:
    context = SecurityContext()
    check("security default mode", context.mode == "ctf_lab" and context.phase == "general")

    context.set_target("http://web-lab.local")
    context.update_phase("enum", 0.87, "发现 Web 目录枚举线索", "检查 /admin")
    context.set_next_action("检查 /admin 的认证逻辑")
    check(
        "security context update",
        context.target == "http://web-lab.local"
        and context.phase == "enum"
        and context.phase_confidence == 0.87
        and context.next_action == "检查 /admin 的认证逻辑",
    )

    evidence = EvidenceStore()
    note = evidence.add_note("登录页返回 debug header", phase=context.phase)
    finding = evidence.add(kind="finding", title="/admin exposed", source="Bash(ffuf)", summary="目录枚举发现 /admin", phase=context.phase)
    rendered = "\n".join(evidence.render_lines())
    check(
        "evidence store",
        evidence.count == 2
        and note.kind == "note"
        and finding.title == "/admin exposed"
        and "登录页返回 debug header" in rendered
        and "/admin exposed" in rendered,
    )

    writeup = build_writeup(context, evidence)
    writeup_ok = "# Challenge" in writeup and "# Evidence" in writeup and "http://web-lab.local" in writeup and "/admin exposed" in writeup
    check("ctf writeup builder", writeup_ok)
```

Call it in `main()` with the other synchronous checks. If there is no explicit `main()` yet, add the call in the existing bottom-level execution sequence wherever `run_transcript_renderer()` is currently called.

Expected final call sequence should include:

```python
run_cli_help()
run_cli_exit()
run_transcript_renderer()
run_security_state()
```

- [ ] **Step 2: Run smoke test and confirm it fails for missing package**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: FAIL with an import error similar to:

```text
ModuleNotFoundError: No module named 'weaver_py.security'
```

- [ ] **Step 3: Checkpoint**

No commit unless explicitly authorized by the user. Record that tests now describe the missing security state layer.

---

## Task 2: Implement `SecurityContext`

**Files:**

- Create: `src/weaver_py/security/__init__.py`
- Create: `src/weaver_py/security/context.py`
- Test: `tests/smoke_python_runtime.py::run_security_state` through the smoke script

- [ ] **Step 1: Create the security package export file**

Create `src/weaver_py/security/__init__.py`:

```python
from .context import SecurityContext
from .evidence import EvidenceItem, EvidenceStore
from .writeup import build_writeup

__all__ = [
    "EvidenceItem",
    "EvidenceStore",
    "SecurityContext",
    "build_writeup",
]
```

This will still fail until `evidence.py` and `writeup.py` exist.

- [ ] **Step 2: Create `SecurityContext`**

Create `src/weaver_py/security/context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from weaver_py.phase import VALID_PHASES


@dataclass
class SecurityContext:
    mode: str = "ctf_lab"
    target: str = ""
    challenge: str = ""
    phase: str = "general"
    phase_confidence: float = 0.0
    phase_reason: str = ""
    current_task: str = ""
    next_action: str = ""

    def set_target(self, value: str) -> None:
        # Target 是安全测试里更自然的术语，这里保留英文，同时只清理首尾空白。
        self.target = value.strip()

    def set_challenge(self, value: str) -> None:
        self.challenge = value.strip()

    def set_next_action(self, value: str) -> None:
        self.next_action = value.strip()

    def update_phase(self, phase: str, confidence: float, reason: str, current_task: str) -> None:
        # 模型或工具可能返回不在枚举里的 phase；这里回落到 general，避免 UI 和 report 崩溃。
        self.phase = phase if phase in VALID_PHASES else "general"
        self.phase_confidence = max(0.0, min(float(confidence), 1.0))
        self.phase_reason = reason.strip()
        self.current_task = current_task.strip()

    def clear(self) -> None:
        self.target = ""
        self.challenge = ""
        self.phase = "general"
        self.phase_confidence = 0.0
        self.phase_reason = ""
        self.current_task = ""
        self.next_action = ""

    def summary_line(self, evidence_count: int = 0) -> str:
        target = self.target or "未设置"
        return f"Lab {self.mode} · Phase {self.phase} · Evidence {evidence_count} · Target {target}"
```

- [ ] **Step 3: Run smoke test and confirm next missing module**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: FAIL with import error for `weaver_py.security.evidence` or `weaver_py.security.writeup`.

- [ ] **Step 4: Checkpoint**

No commit unless explicitly authorized. Confirm `SecurityContext` exists and the next failing test points to evidence/writeup.

---

## Task 3: Implement evidence storage

**Files:**

- Create: `src/weaver_py/security/evidence.py`
- Test: `tests/smoke_python_runtime.py::run_security_state` through the smoke script

- [ ] **Step 1: Create `EvidenceItem` and `EvidenceStore`**

Create `src/weaver_py/security/evidence.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EvidenceItem:
    kind: str
    title: str
    source: str = ""
    summary: str = ""
    phase: str = "general"
    created_at: datetime = field(default_factory=datetime.now)

    def one_line(self) -> str:
        source = f" 来源：{self.source}" if self.source else ""
        summary = f" — {self.summary}" if self.summary else ""
        return f"{self.title} [{self.kind}/{self.phase}]{source}{summary}"


class EvidenceStore:
    def __init__(self) -> None:
        self.items: list[EvidenceItem] = []

    @property
    def count(self) -> int:
        return len(self.items)

    def add(self, kind: str, title: str, source: str = "", summary: str = "", phase: str = "general") -> EvidenceItem:
        item = EvidenceItem(
            kind=kind.strip() or "finding",
            title=title.strip() or "未命名证据",
            source=source.strip(),
            summary=summary.strip(),
            phase=phase.strip() or "general",
        )
        self.items.append(item)
        return item

    def add_note(self, text: str, phase: str = "general") -> EvidenceItem:
        # note 也作为 evidence 保存，P0 阶段减少概念数量，/writeup 可以统一渲染。
        cleaned = text.strip()
        return self.add(kind="note", title=cleaned or "空 note", summary=cleaned, phase=phase)

    def clear(self) -> None:
        self.items.clear()

    def render_lines(self) -> list[str]:
        if not self.items:
            return ["Evidence: 暂无记录。"]
        lines = ["Evidence:"]
        for index, item in enumerate(self.items, start=1):
            lines.append(f"  {index}. {item.title} — {item.phase}")
            if item.source:
                lines.append(f"     来源：{item.source}")
            if item.summary:
                lines.append(f"     摘要：{item.summary}")
        return lines

    def as_markdown(self) -> str:
        if not self.items:
            return "- 暂无 evidence。"
        lines: list[str] = []
        for item in self.items:
            source = f"，来源：{item.source}" if item.source else ""
            summary = f"：{item.summary}" if item.summary else ""
            lines.append(f"- **{item.title}**（{item.kind}/{item.phase}{source}）{summary}")
        return "\n".join(lines)
```

- [ ] **Step 2: Run smoke test and confirm writeup is still missing**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: FAIL with import error for `weaver_py.security.writeup`.

- [ ] **Step 3: Checkpoint**

No commit unless explicitly authorized. Confirm evidence rendering is implemented and only writeup remains missing for this test group.

---

## Task 4: Implement writeup generation

**Files:**

- Create: `src/weaver_py/security/writeup.py`
- Test: `tests/smoke_python_runtime.py::run_security_state` through the smoke script

- [ ] **Step 1: Create writeup builder**

Create `src/weaver_py/security/writeup.py`:

```python
from __future__ import annotations

from .context import SecurityContext
from .evidence import EvidenceStore


def build_writeup(context: SecurityContext, evidence: EvidenceStore) -> str:
    target = context.target or "未设置"
    challenge = context.challenge or "未命名 CTF/lab challenge"
    next_action = context.next_action or "继续根据现有 evidence 推进分析。"
    current_task = context.current_task or "暂无当前任务。"
    phase_reason = context.phase_reason or "暂无阶段判断说明。"

    lines = [
        "# Challenge",
        "",
        challenge,
        "",
        "# Target",
        "",
        target,
        "",
        "# Summary",
        "",
        f"当前模式：`{context.mode}`。当前阶段：`{context.phase}`，置信度：{context.phase_confidence:.2f}。",
        f"阶段判断：{phase_reason}",
        "",
        "# Steps",
        "",
        f"- 当前任务：{current_task}",
        f"- 下一步建议：{next_action}",
        "",
        "# Evidence",
        "",
        evidence.as_markdown(),
        "",
        "# Solution",
        "",
        "根据上面的 evidence 继续补充完整利用路径或解题步骤。",
        "",
        "# Flag / Result",
        "",
        "暂未记录 flag 或最终结果。",
        "",
        "# Lessons Learned",
        "",
        "- 记录本题关键思路、误区和可复用技巧。",
    ]
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 2: Run smoke test and confirm security state passes or reaches next failure**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: `security default mode`, `security context update`, `evidence store`, and `ctf writeup builder` print PASS. Other existing checks may continue after them.

- [ ] **Step 3: Checkpoint**

No commit unless explicitly authorized. The security package is now importable and covered by smoke tests.

---

## Task 5: Wire security state into `WeaverSession`

**Files:**

- Modify: `src/weaver_py/runtime/session.py`
- Test: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add session-level smoke checks before implementation**

In `run_security_state()` after the writeup check, add:

```python
    session = WeaverSession(ROOT)
    session.security.set_target("http://session-target.local")
    session.evidence.add_note("session note", phase="enum")
    session.update_from_event(
        AgentEvent(
            type="phase_update",
            data={"phase": "enum", "confidence": 0.9, "reason": "目录枚举", "current_task": "检查后台路径"},
        )
    )
    status = session.status_plain()
    session_ok = "target=http://session-target.local" in status and "evidence=1" in status and session.security.phase == "enum"
    check("session security state", session_ok)

    session.clear()
    clear_ok = session.security.target == "" and session.evidence.count == 0 and session.security.phase == "general"
    check("session security clear", clear_ok)
```

- [ ] **Step 2: Run smoke test and confirm failure**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: FAIL because `WeaverSession` has no `security` or `evidence` attribute.

- [ ] **Step 3: Modify imports in `session.py`**

Add after existing imports:

```python
from weaver_py.security import EvidenceStore, SecurityContext
```

- [ ] **Step 4: Initialize security state in `WeaverSession.__init__`**

After `self.current_task = ""`, add:

```python
        self.security = SecurityContext()
        self.evidence = EvidenceStore()
```

- [ ] **Step 5: Clear security state in `clear()`**

After `self.tool_events.clear()`, add:

```python
        self.security.clear()
        self.evidence.clear()
```

- [ ] **Step 6: Sync phase events into `SecurityContext`**

In `update_from_event()`, inside the `elif event.type == "phase_update":` block, after `self.current_task = ...`, add:

```python
            self.security.update_phase(self.current_phase, self.phase_confidence, self.phase_reason, self.current_task)
```

- [ ] **Step 7: Extend `status_plain()` with security state**

Replace the return expression with this version:

```python
        target = self.security.target or "-"
        next_action = self.security.next_action or "-"
        return (
            f"phase={self.current_phase} confidence={self.phase_confidence:.2f} "
            f"model={self.config.model} backend={self.config.backend.type}\n"
            f"root={self.root}\n"
            f"mode={self.security.mode} target={target} evidence={self.evidence.count} next_action={next_action}\n"
            f"messages={message_count} tokens={total_tokens} current_task={self.current_task or '-'} "
            f"reason={self.phase_reason or '-'}\n"
            f"skills={len(self.skills)} mcp_servers={len(self.mcp.states)} connected={mcp_connected} failed={mcp_failed}\n"
            f"tools={tools} audit=.weaver/audit/tools.jsonl"
        )
```

- [ ] **Step 8: Run smoke test**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: new `session security state` and `session security clear` checks PASS.

- [ ] **Step 9: Checkpoint**

No commit unless explicitly authorized. `WeaverSession` now owns security state and keeps phase synchronized.

---

## Task 6: Add CTF/lab slash commands

**Files:**

- Modify: `src/weaver_py/runtime/commands.py`
- Modify: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add failing command smoke checks**

In `run_security_state()` after the session clear check, add:

```python
    command_session = WeaverSession(ROOT)
    target_result = handle_command(command_session, "/target http://cmd-target.local")
    note_result = handle_command(command_session, "/note 发现 /admin")
    evidence_result = handle_command(command_session, "/evidence")
    writeup_result = handle_command(command_session, "/writeup")
    command_ok = (
        target_result.handled
        and "Target 已设置" in target_result.message
        and command_session.security.target == "http://cmd-target.local"
        and note_result.handled
        and command_session.evidence.count == 1
        and evidence_result.handled
        and "/admin" in evidence_result.message
        and writeup_result.handled
        and "# Challenge" in writeup_result.message
    )
    check("ctf lab commands", command_ok)
```

- [ ] **Step 2: Run smoke test and confirm unknown command failure**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: FAIL because `/target`, `/note`, `/evidence`, `/writeup` are unknown.

- [ ] **Step 3: Import writeup builder in `commands.py`**

Add after existing imports:

```python
from weaver_py.security import build_writeup
```

- [ ] **Step 4: Extend `COMMANDS`**

Insert after `/permissions` or before `/init`:

```python
    SlashCommand("/target", "设置当前 CTF/lab target"),
    SlashCommand("/note", "添加当前题目 note"),
    SlashCommand("/evidence", "查看当前 evidence"),
    SlashCommand("/writeup", "生成 CTF/lab writeup 草稿"),
```

- [ ] **Step 5: Add command handlers**

In `handle_command()`, before the `/init` branch, add:

```python
    if resolved.name == "/target":
        value = command.removeprefix("/target").strip()
        if not value:
            return CommandResult(handled=True, message="用法：/target <URL、host、文件或题目目标>", is_error=True)
        session.security.set_target(value)
        return CommandResult(handled=True, message=f"Target 已设置：{session.security.target}")

    if resolved.name == "/note":
        value = command.removeprefix("/note").strip()
        if not value:
            return CommandResult(handled=True, message="用法：/note <当前题目笔记>", is_error=True)
        item = session.evidence.add_note(value, phase=session.current_phase)
        return CommandResult(handled=True, message=f"已添加 note：{item.title}")

    if resolved.name == "/evidence":
        return CommandResult(handled=True, message="\n".join(session.evidence.render_lines()))

    if resolved.name == "/writeup":
        return CommandResult(handled=True, message=build_writeup(session.security, session.evidence))
```

- [ ] **Step 6: Run smoke test**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: `ctf lab commands` PASS and `/help` includes the new commands through `COMMANDS`.

- [ ] **Step 7: Checkpoint**

No commit unless explicitly authorized. The CTF/lab command loop exists.

---

## Task 7: Include security state in session reports

**Files:**

- Modify: `src/weaver_py/runtime/report.py`
- Modify: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add failing report assertion**

In `run_report_command()`, after `session = WeaverSession(ROOT)`, add:

```python
    session.security.set_target("http://report-target.local")
    session.evidence.add(kind="finding", title="report evidence", source="manual", summary="报告 smoke 证据", phase="enum")
```

Replace the `ok = ...` line with:

```python
    report_text = result.report_path.read_text(encoding="utf-8") if result.report_path else ""
    ok = (
        result.report_path is not None
        and result.report_path.exists()
        and "Weaver Session Report" in report_text
        and "http://report-target.local" in report_text
        and "report evidence" in report_text
    )
```

- [ ] **Step 2: Run smoke test and confirm report assertion fails**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: `session report command` FAIL because report does not yet include target/evidence.

- [ ] **Step 3: Add security summary to report**

In `generate_session_report()`, after the phase/current task lines in the Summary section, add:

```python
        f"- Mode: `{session.security.mode}`",
        f"- Target: {session.security.target or '-'}",
        f"- Evidence: {session.evidence.count}",
        f"- Next action: {session.security.next_action or '-'}",
```

After the `## Tool Events` block and before `## Files`, add:

```python
    lines.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    lines.extend(session.evidence.render_lines())
```

- [ ] **Step 4: Run smoke test**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: `session report command` PASS.

- [ ] **Step 5: Checkpoint**

No commit unless explicitly authorized. Session reports now include target and evidence summary.

---

## Task 8: Add lab context to CLI status line

**Files:**

- Modify: `src/weaver_py/cli.py`
- Modify: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add a focused status-markup smoke check**

In `tests/smoke_python_runtime.py`, import `_status_markup` near other imports:

```python
from weaver_py.cli import _status_markup
```

Add this function after `run_security_state()`:

```python
def run_cli_lab_status_markup() -> None:
    line = _status_markup(
        label="正在思考",
        started_at=None,
        phase="enum",
        task="检查 /admin",
        input_tokens=10,
        output_tokens=5,
        separator="·",
        lab_context="Lab ctf_lab · Phase enum · Evidence 2 · Target web-lab.local",
    )
    ok = "Lab ctf_lab" in line and "Evidence 2" in line and "Target web-lab.local" in line
    check("cli lab status markup", ok)
```

Call it after `run_security_state()`:

```python
run_cli_lab_status_markup()
```

- [ ] **Step 2: Run smoke test and confirm signature failure**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: FAIL because `_status_markup()` has no `lab_context` parameter.

- [ ] **Step 3: Update `_status_markup()` signature and body**

In `src/weaver_py/cli.py`, change `_status_markup()` signature to include:

```python
    lab_context: str = "",
```

Replace the return line with:

```python
    lab_part = f" {separator} {escape(lab_context)}" if lab_context and escape is not None else (f" {separator} {lab_context}" if lab_context else "")
    return f"[{PALETTE['muted']}]  ⎿ {label} {separator} {_elapsed_text(started_at)}{token_part}{lab_part}[/{PALETTE['muted']}]"
```

- [ ] **Step 4: Pass session lab context from status renderers**

Inside `run_cli()`, after `print_elapsed_line()`, add a helper:

```python
    def lab_context_line() -> str:
        return session.security.summary_line(session.evidence.count)
```

Then update both `_status_markup()` call sites in `print_status()` and `render_status_line()` to pass:

```python
                lab_context=lab_context_line(),
```

For example, `print_status()` should call:

```python
            _status_markup(
                label,
                run_started_at,
                current_phase,
                current_task,
                input_tokens,
                output_tokens,
                separator,
                lab_context=lab_context_line(),
            ),
```

- [ ] **Step 5: Run smoke test**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: `cli lab status markup` PASS.

- [ ] **Step 6: Manually inspect CLI help and a non-interactive exit**

Run:

```bash
python -m weaver_py.cli --help
python -m weaver_py.cli --cwd D:/github_project/Weaver
```

For the second command, type `/exit` if interactive. Expected: no traceback; banner remains readable.

- [ ] **Step 7: Checkpoint**

No commit unless explicitly authorized. CLI now has a restrained lab context line during active turns.

---

## Task 9: Harden OpenAI-compatible streaming/tool_calls

**Files:**

- Modify: `src/weaver_py/agent/engine.py`
- Modify: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add failing unit-style smoke check for chunk merging**

Add this function after `run_cli_lab_status_markup()`:

```python
def run_openai_chunk_merge() -> None:
    engine = AgentEngine(config=WeaverConfig(api_key="test-key", model="gpt-compatible", base_url="http://127.0.0.1:1"), tools=build_default_registry(ROOT))
    merged = engine._merge_chat_chunks(
        [
            {"choices": [{"delta": {"content": "hello "}, "finish_reason": None}]},
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "id": "call_1", "type": "function", "function": {"name": "Read", "arguments": "{\"file"}}
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"name": "", "arguments": "_path\":\"x.py\"}"}}
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            },
        ]
    )
    message = merged["choices"][0]["message"]
    call = message["tool_calls"][0]
    ok = message["content"] == "hello " and call["id"] == "call_1" and call["function"]["name"] == "Read"
    ok = ok and call["function"]["arguments"] == "{\"file_path\":\"x.py\"}" and merged["usage"]["prompt_tokens"] == 3
    check("openai-compatible chunk merge", ok)
```

Call it after `run_cli_lab_status_markup()`:

```python
run_openai_chunk_merge()
```

This may already pass partially. Keep the test because it locks expected behavior.

- [ ] **Step 2: Add failing smoke check for missing tool call id fallback**

Extend `run_openai_chunk_merge()` with:

```python
    fallback = engine._merge_chat_chunks(
        [
            {
                "choices": [
                    {
                        "delta": {"tool_calls": [{"index": 0, "function": {"name": "Glob", "arguments": "{\"pattern\":\"*.py\"}"}}]},
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        ]
    )
    fallback_call = fallback["choices"][0]["message"]["tool_calls"][0]
    fallback_ok = fallback_call["id"] == "call_0" and fallback_call["function"]["name"] == "Glob"
    check("openai-compatible missing id fallback", fallback_ok)
```

Expected before implementation: FAIL because current merge returns empty id.

- [ ] **Step 3: Update `_merge_chat_chunks()` with fallback ids and Chinese comments**

In `engine.py`, replace `_merge_chat_chunks()` with:

```python
    def _merge_chat_chunks(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        # OpenAI-compatible 网关经常把 content、tool_calls.name、tool_calls.arguments 分片返回。
        # 这里把 streaming delta 合并成普通 chat completion 形状，后面的 tool loop 就不用关心网关差异。
        content: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] = {}
        for chunk in chunks:
            if isinstance(chunk.get("usage"), dict):
                usage = chunk["usage"]
            for choice in chunk.get("choices") or []:
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    content.append(str(delta["content"]))
                for tool_delta in delta.get("tool_calls") or []:
                    index = int(tool_delta.get("index") or 0)
                    existing = tool_calls_by_index.setdefault(
                        index,
                        {"id": f"call_{index}", "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    if tool_delta.get("id"):
                        existing["id"] = str(tool_delta["id"])
                    if tool_delta.get("type"):
                        existing["type"] = str(tool_delta["type"])
                    function_delta = tool_delta.get("function") or {}
                    if function_delta.get("name"):
                        existing["function"]["name"] += str(function_delta["name"])
                    if function_delta.get("arguments"):
                        existing["function"]["arguments"] += str(function_delta["arguments"])
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "".join(content),
                        "tool_calls": [tool_calls_by_index[index] for index in sorted(tool_calls_by_index)],
                    },
                    "finish_reason": finish_reason,
                }
            ],
            "usage": usage,
        }
```

- [ ] **Step 4: Make `_ask_chat_completions()` tolerate missing usage and malformed arguments**

In `_ask_chat_completions()`, replace the JSON argument parsing block:

```python
                try:
                    tool_input = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                except json.JSONDecodeError:
                    tool_input = {}
```

with:

```python
                try:
                    tool_input = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                except json.JSONDecodeError:
                    # 有些兼容网关会在 tool_calls.arguments 上返回不完整 JSON；先给工具空参数，
                    # 同时保留后续错误在 transcript 中暴露，避免整个 agent loop 直接崩溃。
                    tool_input = {}
```

Keep existing behavior, but add the Chinese comment so future readers know this is compatibility handling.

- [ ] **Step 5: Run smoke test**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: `openai-compatible chunk merge` and `openai-compatible missing id fallback` PASS.

- [ ] **Step 6: Checkpoint**

No commit unless explicitly authorized. OpenAI-compatible chunk merge behavior is now locked by smoke tests.

---

## Task 10: Update user-facing docs

**Files:**

- Modify: `README.md`
- Modify: `PROJECT_OVERVIEW.md`
- Modify: `ROADMAP.md`
- Modify: `HANDOFF.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `README.md`**

Revise the introduction to say Weaver is OpenAI-compatible-first and CTF/lab-focused. Add the new commands under “常用 slash commands”:

```markdown
- `/target <value>`：设置当前 CTF/lab target
- `/note <text>`：添加当前题目 note
- `/evidence`：查看当前 evidence
- `/writeup`：生成 CTF/lab writeup 草稿
```

Add a short note under configuration:

```markdown
模型接入优先支持 OpenAI-compatible `base_url + model + /v1/chat/completions`，Claude Messages API 保留为兼容路径。
```

- [ ] **Step 2: Update `PROJECT_OVERVIEW.md`**

Add the new architecture layer:

```text
weaver_py.cli
  -> WeaverSession
      -> AgentEngine
      -> SecurityContext / EvidenceStore / WriteupBuilder
      -> ToolRegistry
      -> SkillLoader
      -> McpManager
      -> Report / Audit
```

Add a `src/weaver_py/security/*` section describing context, evidence, and writeup.

- [ ] **Step 3: Update `ROADMAP.md`**

Replace the old P0 item “补齐 Claude Messages API 原生 streaming 的完整路径” with:

```markdown
- OpenAI-compatible streaming / tool_calls 主路径稳定化
- CTF/lab target、note、evidence、writeup 最小闭环
- 安全实验室风格 CLI 状态层
```

Move Claude Messages API native streaming to P2 compatibility work.

- [ ] **Step 4: Update `HANDOFF.md`**

Add current progress and next steps:

```markdown
- 当前主线已调整为 OpenAI-compatible 优先、CTF/lab 优先。
- P0 新增 security context、evidence、writeup 和安全实验室 CLI 状态层。
- 实现时用户要求关键逻辑写详细中文注释，提示语中文友好，但 Bash、shell、streaming、tool_calls 等技术词不硬翻译。
```

- [ ] **Step 5: Update `CLAUDE.md`**

Add durable project instructions:

```markdown
- Weaver 模型主线是 OpenAI-compatible，Claude Messages API 是兼容路径。
- 做 UI/CLI/TUI 相关修改前先调用相关 UI/design skills。
- 关键流程写中文注释，用户可见提示语用自然中文；Bash、shell、streaming、tool_calls 等技术词不硬翻译。
```

- [ ] **Step 6: Run documentation grep checks**

Run:

```bash
python -m compileall -q D:/github_project/Weaver/src/weaver_py
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: both commands exit 0.

- [ ] **Step 7: Checkpoint**

No commit unless explicitly authorized. Docs now match implemented behavior.

---

## Task 11: Manual CLI verification

**Files:**

- No source edits expected unless verification finds a bug.

- [ ] **Step 1: Run compileall**

Run:

```bash
python -m compileall -q D:/github_project/Weaver/src/weaver_py
```

Expected: exit 0 with no output.

- [ ] **Step 2: Run smoke script**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: all checks print PASS.

- [ ] **Step 3: Check CLI help**

Run:

```bash
python -m weaver_py.cli --help
```

Expected: exit 0 and help text shows Weaver Python runtime.

- [ ] **Step 4: Check interactive command flow**

Run:

```bash
python -m weaver_py.cli --cwd D:/github_project/Weaver
```

Type these commands manually:

```text
/status
/target http://web-lab.local
/note 发现 /admin 可疑路径
/evidence
/writeup
/exit
```

Expected:

- `/status` includes `mode=ctf_lab`, `target`, and `evidence`.
- `/target` prints `Target 已设置`.
- `/note` prints `已添加 note`.
- `/evidence` shows the note.
- `/writeup` prints Markdown sections.
- `/exit` exits normally and saves a report if there was interaction.

- [ ] **Step 5: Inspect UI quality**

Expected UI qualities:

- No repeated user input echo in interactive mode.
- Lab context appears as a restrained single-line status, not a large repeated panel.
- No large purple surfaces.
- Chinese prompts are natural.
- Technical terms like Bash, shell, Target, Evidence, writeup are not awkwardly translated.

- [ ] **Step 6: Fix any verification failure with a new tiny task**

If a command fails, add a narrow test to `tests/smoke_python_runtime.py`, reproduce the failure, then fix the smallest relevant file. Do not make unrelated refactors.

---

## Self-Review

Spec coverage:

- OpenAI-compatible-first direction: covered by Task 9 and docs in Task 10.
- CTF/lab state: covered by Tasks 1-5.
- `/target`, `/note`, `/evidence`, `/writeup`: covered by Task 6.
- Report/writeup distinction: covered by Tasks 4, 7, and 10.
- Security-lab UI: covered by Task 8 and manual verification in Task 11.
- Chinese comments and friendly Chinese prompts while preserving technical terms: covered in Tasks 2, 3, 9, 10, and 11.
- Documentation sync: covered by Task 10.

Placeholder scan:

- This plan intentionally avoids TODO/TBD placeholders.
- Code blocks define concrete functions/classes/commands.
- Any future bug found during verification must become a new narrow test-backed task.

Type consistency:

- `SecurityContext`, `EvidenceStore`, `EvidenceItem`, and `build_writeup` are exported from `weaver_py.security` and used consistently.
- `session.security` and `session.evidence` are the only new session attributes.
- Slash commands call methods defined in the security package.
