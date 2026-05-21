from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class ToolRegistry:
    def __init__(
        self,
        tools: Iterable[BaseTool] | None = None,
        max_model_output: int = 20_000,
        audit_path: Path | None = None,
    ):
        self._tools: dict[str, BaseTool] = {}
        self.max_model_output = max_model_output
        self.audit_path = audit_path
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, object]]:
        return [tool.schema() for tool in self._tools.values()]

    async def execute(self, name: str, input: dict[str, object]) -> ToolResult:
        # Every tool call passes through here so truncation and audit behavior stay consistent.
        tool = self._tools.get(name)
        if tool is None:
            result = ToolResult(output=f"Unknown tool: {name}", exit_code=1, is_error=True)
            self._write_audit(name, input, result)
            return result
        try:
            result = await tool.execute(input)
        except Exception as exc:
            result = ToolResult(output=f"Tool {name} failed: {exc}", exit_code=1, is_error=True)
        truncated = self._truncate(result)
        self._write_audit(name, input, truncated)
        return truncated

    def _truncate(self, result: ToolResult) -> ToolResult:
        output = result.output
        if len(output) <= self.max_model_output:
            return result
        truncated = output[: self.max_model_output]
        suffix = f"\n\n[output truncated: {len(output) - self.max_model_output} characters omitted]"
        return ToolResult(
            output=truncated + suffix,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            is_error=result.is_error,
        )

    def _write_audit(self, name: str, input: dict[str, object], result: ToolResult) -> None:
        # Audit records keep a redacted preview, not the full tool output.
        if self.audit_path is None:
            return
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "tool": name,
            "input": self._redact(input),
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "is_error": result.is_error,
            "output_preview": result.output[:1000],
        }
        with self.audit_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _redact(self, value: object) -> object:
        if isinstance(value, dict):
            redacted: dict[str, object] = {}
            for key, item in value.items():
                lower = str(key).lower()
                if "key" in lower or "token" in lower or "password" in lower or "secret" in lower:
                    redacted[str(key)] = "[REDACTED]"
                else:
                    redacted[str(key)] = self._redact(item)
            return redacted
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value
