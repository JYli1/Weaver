# Windows PowerShell Tool Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a native `PowerShell` tool for Windows, make Windows sessions prefer `PowerShell`, and keep `Bash` available for compatibility without coupling this work to the separate OpenAI-compatible `reasoning_content` replay fix.

**Architecture:** Introduce a dedicated `PowerShellTool` beside `BashTool`, reuse the existing `CommandPolicy`, and choose tool registration order by platform in `build_default_registry()`. Bias model behavior with tool descriptions and a short Windows-specific rule in the system prompt rather than changing the whole tool loop.

**Tech Stack:** Python 3.11+, asyncio subprocess, Windows PowerShell 5.1, existing Weaver `ToolRegistry`, smoke tests in `tests/smoke_python_runtime.py`

---

## File Structure

- **Create:** `src/weaver_py/tools/powershell.py`
  - Single responsibility: execute Windows-native shell commands through `powershell.exe` with the shared safety policy and the same input contract as `BashTool`.

- **Modify:** `src/weaver_py/tools/__init__.py`
  - Export `PowerShellTool`.

- **Modify:** `src/weaver_py/runtime/tools.py`
  - Register `PowerShellTool` before `BashTool` on Windows; keep Unix-like platforms unchanged.

- **Modify:** `src/weaver_py/agent/engine.py`
  - Add a narrow Windows-specific shell selection rule to the system prompt only. Do not mix in the separate `reasoning_content` compatibility work here.

- **Modify:** `src/weaver_py/ui/transcript.py`
  - Render `PowerShell(...)` with the same preview/summarization behavior as `Bash(...)`.

- **Modify:** `src/weaver_py/runtime/commands.py`
  - Update `/permissions` and `/init` help text so they no longer imply Bash is the only shell tool.

- **Modify/Test:** `tests/smoke_python_runtime.py`
  - Add smoke checks for registry order, transcript rendering, and Windows-gated `PowerShellTool` execution.

---

### Task 1: Add `PowerShellTool`

**Files:**
- Create: `src/weaver_py/tools/powershell.py`
- Reuse reference: `src/weaver_py/tools/bash.py`
- Reuse policy: `src/weaver_py/safety/policy.py`
- Test: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Write the failing smoke check**

Add this helper near the other tool smoke helpers in `tests/smoke_python_runtime.py`:

```python
def run_powershell_tool_smoke() -> None:
    if sys.platform != "win32":
        check("powershell tool", True, "skipped on non-Windows")
        return
```

Then, inside `run_tools()`, add a failing assertion block after the existing `bash tool` check:

```python
    if sys.platform == "win32":
        powershell_result = await registry.execute(
            "PowerShell",
            {"command": "$value = 7; Write-Output \"ps-$value\""},
        )
        check("powershell tool", powershell_result.exit_code == 0 and "ps-7" in powershell_result.output)
```

- [ ] **Step 2: Run smoke to verify it fails**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected on Windows: FAIL at `powershell tool` because `PowerShell` is not yet registered.

- [ ] **Step 3: Create `PowerShellTool` with shared input schema**

Create `src/weaver_py/tools/powershell.py` with this implementation:

```python
from __future__ import annotations

import asyncio
import locale
import sys
from pathlib import Path

from weaver_py.safety import CommandPolicy

from .base import BaseTool, ToolResult


def _decode_output(data: bytes) -> str:
    encodings = ["utf-8", locale.getpreferredencoding(False)]
    if sys.platform == "win32":
        encodings.extend(["cp936", "gbk", "mbcs"])
    for encoding in dict.fromkeys(encodings):
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode(errors="replace")


class PowerShellTool(BaseTool):
    name = "PowerShell"
    description = "Execute a Windows PowerShell command with Weaver safety policy checks. Prefer this tool on Windows for shell tasks."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "PowerShell command to execute."},
            "timeout": {"type": "integer", "description": "Timeout in milliseconds."},
            "cwd": {"type": "string", "description": "Working directory."},
            "confirmed": {"type": "boolean", "description": "Whether the user confirmed a risky command."},
        },
        "required": ["command"],
    }

    def __init__(self, policy: CommandPolicy | None = None, default_timeout_ms: int = 120_000):
        self.policy = policy or CommandPolicy()
        self.default_timeout_ms = default_timeout_ms

    async def execute(self, input: dict[str, object]) -> ToolResult:
        command = input.get("command")
        if not isinstance(command, str):
            return ToolResult("command must be a string", 1, is_error=True)
        confirmed = bool(input.get("confirmed") or False)
        decision = self.policy.evaluate(command, confirmed=confirmed)
        if decision.decision == "deny":
            return ToolResult(f"Command denied: {decision.reason}", 1, is_error=True)
        if decision.decision == "ask":
            return ToolResult(f"Command requires confirmation: {decision.reason}", 1, is_error=True)
        timeout_ms = int(input.get("timeout") or self.default_timeout_ms)
        cwd_value = input.get("cwd")
        cwd = str(Path(str(cwd_value)).expanduser()) if isinstance(cwd_value, str) else None
        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult("Command timed out", 1, timed_out=True, is_error=True)
        except OSError as exc:
            return ToolResult(f"Command failed to start: {exc}", 1, is_error=True)
        output = _decode_output(stdout)
        err = _decode_output(stderr)
        combined = output if not err else f"{output}\n{err}".strip()
        return ToolResult(combined, proc.returncode or 0, is_error=(proc.returncode or 0) != 0)
```

- [ ] **Step 4: Export the new tool**

Modify `src/weaver_py/tools/__init__.py`:

```python
from .bash import BashTool
from .edit import EditTool
from .glob import GlobTool
from .grep import GrepTool
from .mcp import McpToolAdapter
from .phase import UpdatePhaseTool
from .powershell import PowerShellTool
from .read import ReadTool
from .registry import ToolRegistry
from .skill import SkillTool
from .write import WriteTool

__all__ = [
    "BashTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "McpToolAdapter",
    "PowerShellTool",
    "ReadTool",
    "SkillTool",
    "ToolRegistry",
    "UpdatePhaseTool",
    "WriteTool",
]
```

- [ ] **Step 5: Run smoke to verify the new tool works**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected on Windows: `powershell tool` PASS.

---

### Task 2: Register PowerShell first on Windows

**Files:**
- Modify: `src/weaver_py/runtime/tools.py`
- Test: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add a failing registry-order smoke check**

Add this helper to `tests/smoke_python_runtime.py`:

```python
def run_shell_registry_order() -> None:
    registry = build_default_registry(ROOT)
    names = [schema["name"] for schema in registry.schemas()]
    if sys.platform == "win32":
        ok = "PowerShell" in names and "Bash" in names and names.index("PowerShell") < names.index("Bash")
        check("shell registry order", ok)
    else:
        check("shell registry order", "Bash" in names and "PowerShell" not in names)
```
```

Call it from `main()` before `run_tools()`.

- [ ] **Step 2: Run smoke to verify it fails**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected on Windows: FAIL at `shell registry order` because `PowerShell` is not yet registered in `build_default_registry()`.

- [ ] **Step 3: Register tools by platform**

Modify `src/weaver_py/runtime/tools.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

from weaver_py.tools import BashTool, EditTool, GlobTool, GrepTool, PowerShellTool, ReadTool, ToolRegistry, UpdatePhaseTool, WriteTool


def build_default_registry(root: Path | None = None, audit_name: str = "tools.jsonl") -> ToolRegistry:
    audit_path = (root / ".weaver" / "audit" / audit_name) if root else None
    shell_tools = [PowerShellTool(), BashTool()] if sys.platform == "win32" else [BashTool()]
    return ToolRegistry(
        [UpdatePhaseTool(), ReadTool(), WriteTool(), EditTool(), GlobTool(), GrepTool(), *shell_tools],
        audit_path=audit_path,
    )
```

- [ ] **Step 4: Run smoke to verify registration order**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected:
- Windows: `shell registry order` PASS with `PowerShell` before `Bash`
- Non-Windows: `shell registry order` PASS with only `Bash`

---

### Task 3: Bias Windows sessions toward PowerShell

**Files:**
- Modify: `src/weaver_py/tools/bash.py`
- Modify: `src/weaver_py/agent/engine.py`
- Test: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add a failing description-focused smoke check**

Add this helper to `tests/smoke_python_runtime.py`:

```python
def run_shell_tool_descriptions() -> None:
    registry = build_default_registry(ROOT)
    descriptions = {schema["name"]: str(schema["description"]) for schema in registry.schemas()}
    if sys.platform == "win32":
        ok = "PowerShell" in descriptions and "Prefer this tool on Windows" in descriptions["PowerShell"]
        ok = ok and "Windows" in descriptions["Bash"]
        check("shell tool descriptions", ok)
    else:
        check("shell tool descriptions", "Bash" in descriptions)
```
```

Call it from `main()` after `run_shell_registry_order()`.

- [ ] **Step 2: Run smoke to verify it fails**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected on Windows: FAIL because `BashTool.description` does not yet explain Windows limitations.

- [ ] **Step 3: Narrow the Bash description**

Modify `src/weaver_py/tools/bash.py`:

```python
class BashTool(BaseTool):
    name = "Bash"
    description = "Execute a POSIX-style shell command with Weaver safety policy checks. On Windows this may run through the system shell and may not support bash-specific syntax unless an external bash environment is available."
```

Do not change the execution behavior yet in this task.

- [ ] **Step 4: Add a Windows-specific prompt rule**

Append these lines to `BASE_SYSTEM_PROMPT` in `src/weaver_py/agent/engine.py` after the existing output rules block:

```python
- On Windows, prefer the PowerShell tool for shell tasks.
- Use Bash only for POSIX-style commands or when the user explicitly asks for bash syntax.
```

This is intentionally narrow: it changes model bias only, not the tool loop or chat protocol.

- [ ] **Step 5: Run smoke to verify description checks pass**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected on Windows: `shell tool descriptions` PASS.

---

### Task 4: Make transcript and help text aware of PowerShell

**Files:**
- Modify: `src/weaver_py/ui/transcript.py`
- Modify: `src/weaver_py/runtime/commands.py`
- Test: `tests/smoke_python_runtime.py`

- [ ] **Step 1: Add failing transcript smoke coverage**

Add this block to `run_transcript_renderer()` in `tests/smoke_python_runtime.py`:

```python
    powershell_start = renderer.render_event(
        AgentEvent(type="tool_start", data={"id": "ps-1", "name": "PowerShell", "input": {"command": "Write-Output hello"}})
    )
    powershell_done = renderer.render_event(
        AgentEvent(type="tool_result", data={"id": "ps-1", "name": "PowerShell", "exit_code": 0, "output": "hello"})
    )
```

And include them in the joined output plus the assertion:

```python
    rendered = "\n".join(
        write_start + write_done + edit_start + edit_done + bash_start + bash_error + read_start + read_done + skill_start + skill_done + mcp_start + mcp_done + powershell_start + powershell_done
    )
    ok = ok and "PowerShell(" in rendered
```

- [ ] **Step 2: Run smoke to verify it fails**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected: FAIL because `TranscriptRenderer._tool_title()` does not yet special-case `PowerShell`.

- [ ] **Step 3: Add PowerShell transcript handling**

Modify `src/weaver_py/ui/transcript.py` in `_tool_title()`, `_summarize_result()`, and `_should_preview()`:

```python
        if name == "PowerShell":
            return f"PowerShell({self._shorten(str(tool_input.get('command') or ''), 80)})"
```

```python
        if name == "PowerShell":
            return f"exit={exit_code}, {self._line_count(output)} lines"
```

```python
        return failed or name in {"Read", "Glob", "Grep", "Bash", "PowerShell", "Skill"} or self._mcp_title(name) is not None
```

- [ ] **Step 4: Update help and permissions text**

Modify `src/weaver_py/runtime/commands.py`:

```python
def _permissions_message(session: Any) -> str:
    return (
        "权限：\n"
        "  Shell 工具安全策略已启用，破坏性或高风险命令会被拒绝或要求确认。\n"
        "  工具调用会写入审计日志，敏感字段会先做脱敏。\n"
        "  审计日志：.weaver/audit/tools.jsonl\n"
        "  当前版本暂不保存按工具划分的 allowlist。"
    )
```

And in `_init_message()` update the sample allowed tools line:

```python
"  allowed-tools: [Read, Grep, Bash, PowerShell]\n"
```

- [ ] **Step 5: Run smoke to verify transcript/help compatibility**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected:
- `transcript renderer` PASS with `PowerShell(` present
- Existing command/help smoke still passes

---

### Task 5: Final verification and scope guard

**Files:**
- Verify only; no new feature files
- Note open follow-up: `src/weaver_py/agent/engine.py` `reasoning_content` replay issue remains separate work

- [ ] **Step 1: Run compile verification**

Run:

```bash
python -m compileall -q D:/github_project/Weaver/src/weaver_py
```

Expected: no output, exit 0.

- [ ] **Step 2: Run full smoke suite**

Run:

```bash
python D:/github_project/Weaver/tests/smoke_python_runtime.py
```

Expected additions:
- `shell registry order` PASS
- `shell tool descriptions` PASS
- `powershell tool` PASS on Windows or skipped on non-Windows
- `transcript renderer` PASS with `PowerShell(` support

- [ ] **Step 3: Manual Windows verification**

Run:

```bash
python -m weaver_py.cli --cwd D:/github_project/Weaver
```

Then prompt:

```text
执行一个 PowerShell 打印 hello 的命令
```

Expected:
- Model should prefer `PowerShell(...)` rather than `Bash(...)`
- Transcript should show `PowerShell(...)`
- Command output should render without cmd/bash syntax confusion

- [ ] **Step 4: Confirm scope isolation**

Do not modify `reasoning_content` replay in this plan. If chat/tool second-round 400 still occurs, track it as separate follow-up work after shell support lands.

- [ ] **Step 5: Commit**

```bash
git add src/weaver_py/tools/powershell.py src/weaver_py/tools/__init__.py src/weaver_py/runtime/tools.py src/weaver_py/tools/bash.py src/weaver_py/agent/engine.py src/weaver_py/ui/transcript.py src/weaver_py/runtime/commands.py tests/smoke_python_runtime.py
git commit -m "feat: add Windows PowerShell shell tool"
```

Expected: commit created with only shell-support changes.

---

## Self-Review

- **Spec coverage:** This plan covers the new PowerShell tool, platform-specific registration, model bias, transcript/help integration, and smoke coverage. It intentionally does **not** solve the separate OpenAI-compatible `reasoning_content` replay bug.
- **Placeholder scan:** No TODO/TBD placeholders remain. Each task contains concrete file paths, code, commands, and expected outcomes.
- **Type consistency:** `PowerShellTool`, `BannerContext`, `ToolRegistry`, and smoke helper names are consistent across tasks. Input schema matches `BashTool` so the existing tool loop can reuse it without protocol changes.

Plan complete and saved to `docs/superpowers/plans/2026-05-23-windows-powershell-tool-support.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?