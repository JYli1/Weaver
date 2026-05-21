from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from rich.markup import escape

from weaver_py.agent.events import AgentEvent
from weaver_py.tui.theme import PALETTE

PENDING_CIRCLE = "○"
SUCCESS_CIRCLE = "●"
FAILURE_CIRCLE = "●"
RESULT_PREFIX = "  ⎿ "


@dataclass
class ToolCallView:
    name: str
    input: dict[str, Any] = field(default_factory=dict)


class TranscriptRenderer:
    def __init__(self, unicode: bool = True) -> None:
        self._tool_calls: dict[str, ToolCallView] = {}
        self.pending_circle = PENDING_CIRCLE if unicode else "*"
        self.success_circle = SUCCESS_CIRCLE if unicode else "*"
        self.failure_circle = FAILURE_CIRCLE if unicode else "*"
        self.result_prefix = RESULT_PREFIX if unicode else "  | "
        self.success = "✓" if unicode else "OK"
        self.failure = "✗" if unicode else "ERR"
        self.ellipsis = "…" if unicode else "..."

    def render_event(self, event: AgentEvent) -> list[str]:
        if event.type in {"tool_start", "tool_result", "tool_error"} and event.data.get("name") == "UpdatePhase":
            return []
        if event.type == "tool_start":
            return self._render_tool_start(event)
        if event.type in {"tool_result", "tool_error"}:
            return self._render_tool_result(event, is_error=event.type == "tool_error")
        if event.type == "phase_update":
            phase = str(event.data.get("phase") or "general")
            task = str(event.data.get("current_task") or "")
            suffix = f" · {escape(task)}" if task else ""
            return [f"[{PALETTE['muted']}]{self.result_prefix}阶段：[/{PALETTE['muted']}][{PALETTE['accent_2']}]{escape(phase)}[/{PALETTE['accent_2']}][{PALETTE['muted']}]{suffix}[/{PALETTE['muted']}]"]
        if event.type == "context_warning":
            return [f"[{PALETTE['muted']}]{self.result_prefix}上下文：{escape(str(event.data.get('level') or ''))}[/{PALETTE['muted']}]"]
        if event.type == "progress_saved":
            return [f"[{PALETTE['muted']}]{self.result_prefix}进度已保存：{escape(str(event.data.get('path') or ''))}[/{PALETTE['muted']}]"]
        return []

    def _render_tool_start(self, event: AgentEvent) -> list[str]:
        tool_id = str(event.data.get("id") or event.data.get("name") or "tool")
        name = str(event.data.get("name") or "tool")
        raw_input = event.data.get("input")
        tool_input = raw_input if isinstance(raw_input, dict) else {}
        self._tool_calls[tool_id] = ToolCallView(name=name, input=tool_input)
        title = self._tool_title(name, tool_input)
        return [f"[{PALETTE['muted']}]{self.pending_circle}[/{PALETTE['muted']}] [{PALETTE['text']}]{escape(title)}[/{PALETTE['text']}]"]

    def _render_tool_result(self, event: AgentEvent, is_error: bool) -> list[str]:
        tool_id = str(event.data.get("id") or event.data.get("name") or "tool")
        name = str(event.data.get("name") or "tool")
        call = self._tool_calls.get(tool_id) or ToolCallView(name=name)
        output = str(event.data.get("output") or "")
        exit_code = int(event.data.get("exit_code") or 0)
        failed = is_error or exit_code != 0
        title = self._tool_title(call.name, call.input)
        if failed:
            first = self._first_line(output) or f"exit={exit_code}"
            summary = f"{title} · Error: {first}"
            summary_markup = f"[{PALETTE['error']}]{self.failure_circle}[/{PALETTE['error']}] [{PALETTE['text']}]{escape(summary)}[/{PALETTE['text']}]"
        else:
            summary = f"{title} · {self._summarize_result(call.name, call.input, output, exit_code)}"
            summary_markup = f"[{PALETTE['success']}]{self.success_circle}[/{PALETTE['success']}] [{PALETTE['text']}]{escape(summary)}[/{PALETTE['text']}]"
        lines = [summary_markup]
        if self._should_preview(call.name, output, failed):
            lines.extend(f"      [{PALETTE['muted']}]{escape(line)}[/{PALETTE['muted']}]" for line in self._preview_lines(output))
        return lines

    def _tool_title(self, name: str, tool_input: dict[str, Any]) -> str:
        if name == "Skill":
            return f"Skill({tool_input.get('skill') or ''})"
        mcp_title = self._mcp_title(name)
        if mcp_title:
            return f"MCP {mcp_title}"
        if name in {"Read", "Write", "Edit"}:
            return f"{name}({self._short_path(str(tool_input.get('file_path') or ''))})"
        if name == "Bash":
            return f"Bash({self._shorten(str(tool_input.get('command') or ''), 80)})"
        if name == "Glob":
            return f"Glob({tool_input.get('pattern') or '*'})"
        if name == "Grep":
            return f"Grep({tool_input.get('pattern') or ''})"
        if name == "UpdatePhase":
            return f"UpdatePhase({tool_input.get('phase') or 'general'})"
        return f"{name}({self._shorten(json.dumps(tool_input, ensure_ascii=False), 80)})"

    def _summarize_result(self, name: str, tool_input: dict[str, Any], output: str, exit_code: int) -> str:
        if name == "Skill":
            skill = self._metadata_value(output, "Skill") or str(tool_input.get("skill") or "skill")
            source = self._metadata_value(output, "Source") or "project"
            return f"Loaded skill: {skill} · {source}"
        mcp_title = self._mcp_title(name)
        if mcp_title:
            return f"MCP {mcp_title} returned {self._line_count(output)} lines"
        if name == "Read":
            return f"Read {self._line_count(output)} lines"
        if name == "Write":
            content = str(tool_input.get("content") or "")
            return f"Added {self._line_count(content)} lines · {len(content)} chars"
        if name == "Edit":
            old = str(tool_input.get("old_string") or "")
            new = str(tool_input.get("new_string") or "")
            added = max(self._line_count(new) - self._line_count(old), 0)
            removed = max(self._line_count(old) - self._line_count(new), 0)
            replacement = self._first_line(output)
            if added or removed:
                return f"{replacement} · Added {added} lines, removed {removed} lines"
            return replacement
        if name == "Glob":
            return f"Found {self._non_empty_line_count(output)} files"
        if name == "Grep":
            return f"Found {self._non_empty_line_count(output)} matches"
        if name == "Bash":
            return f"exit={exit_code}, {self._line_count(output)} lines"
        if name == "UpdatePhase":
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                return self._first_line(output)
            phase = data.get("phase", "general")
            task = data.get("current_task") or ""
            suffix = f" · {task}" if task else ""
            return f"Phase: {phase}{suffix}"
        return self._first_line(output)

    def _short_path(self, value: str) -> str:
        if not value:
            return ""
        normalized = value.replace("\\", "/")
        parts = normalized.split("/")
        if len(parts) <= 3:
            return value
        return "/".join(parts[-3:])

    def _line_count(self, text: str) -> int:
        if text == "":
            return 0
        return len(text.splitlines()) or 1

    def _non_empty_line_count(self, text: str) -> int:
        return sum(1 for line in text.splitlines() if line.strip())

    def _first_line(self, text: str) -> str:
        line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return self._shorten(line, 180)

    def _should_preview(self, name: str, output: str, failed: bool) -> bool:
        if not output.strip():
            return False
        return failed or name in {"Read", "Glob", "Grep", "Bash", "Skill"} or self._mcp_title(name) is not None

    def _preview_lines(self, text: str, max_lines: int = 4, max_chars: int = 520) -> list[str]:
        lines: list[str] = []
        used = 0
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("Skill:", "Description:", "Source:")):
                continue
            if line.startswith("Base directory for this skill:"):
                line = "Base: " + line.split(":", 1)[1].strip()
            remaining = max_chars - used
            if remaining <= 0 or len(lines) >= max_lines:
                break
            shortened = self._shorten(line, min(remaining, 160))
            lines.append(shortened)
            used += len(shortened)
        if self._non_empty_line_count(text) > len(lines):
            lines.append(self.ellipsis)
        return lines

    def _shorten(self, text: str, limit: int) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit] + self.ellipsis

    def _metadata_value(self, output: str, key: str) -> str:
        prefix = f"{key}:"
        for line in output.splitlines():
            if line.startswith(prefix):
                return line.split(":", 1)[1].strip()
        return ""

    def _mcp_title(self, name: str) -> str | None:
        if not name.startswith("mcp__"):
            return None
        parts = name.split("__", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            return None
        return f"{parts[1]}.{parts[2]}"
