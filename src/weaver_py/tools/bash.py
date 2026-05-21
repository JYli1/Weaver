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


class BashTool(BaseTool):
    name = "Bash"
    description = "Execute a local shell command with Weaver safety policy checks."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command to execute."},
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
            proc = await asyncio.create_subprocess_shell(
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
