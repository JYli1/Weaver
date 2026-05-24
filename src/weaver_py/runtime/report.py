from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def save_session_report(session: Any, reason: str = "manual") -> Path | None:
    if not session.has_interaction():
        return None
    report_dir = session.report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    path = _next_report_path(report_dir, now)
    path.write_text(generate_session_report(session, now, reason), encoding="utf-8")
    return path


def generate_session_report(session: Any, ended_at: datetime, reason: str) -> str:
    messages = session.engine.conversation.messages
    user_count = sum(1 for message in messages if message.get("role") == "user")
    assistant_count = sum(1 for message in messages if message.get("role") == "assistant")
    tool_result_count = _count_tool_results(messages)
    elapsed = ended_at - session.started_at
    lines = [
        "# Weaver Session Report",
        "",
        "## Summary",
        "",
        f"- Reason: {reason}",
        f"- Started: {session.started_at.isoformat(timespec='seconds')}",
        f"- Ended: {ended_at.isoformat(timespec='seconds')}",
        f"- Duration: {str(elapsed).split('.')[0]}",
        f"- Root: `{session.root}`",
        f"- Model: `{session.config.model}`",
        f"- Backend: `{session.config.backend.type}`",
        f"- Tokens: input={session.input_tokens}, output={session.output_tokens}, total={session.input_tokens + session.output_tokens}",
        f"- Phase: `{session.current_phase}` confidence={session.phase_confidence:.2f}",
        f"- Mode: `{session.security.mode}`",
        f"- Target: {session.security.target or '-'}",
        f"- Evidence: {session.evidence.count}",
        f"- Next action: {session.security.next_action or '-'}",
        f"- Current task: {session.current_task or '-'}",
        f"- Phase reason: {session.phase_reason or '-'}",
        "",
        "## Conversation",
        "",
        f"- User messages: {user_count}",
        f"- Assistant messages: {assistant_count}",
        f"- Tool result blocks: {tool_result_count}",
        "",
        "## Recent Timeline",
        "",
    ]
    lines.extend(_render_recent_messages(messages[-12:]))
    lines.extend(
        [
            "",
            "## Tool Events",
            "",
        ]
    )
    if session.tool_events:
        for event in session.tool_events[-20:]:
            name = event.get("name") or "tool"
            if event.get("type") == "start":
                lines.append(f"- start `{name}`")
            else:
                output = _single_line(str(event.get("output") or ""), 160)
                lines.append(f"- {event.get('type')} `{name}` exit={event.get('exit_code')} {output}")
    else:
        lines.append("- No tool events recorded.")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    lines.extend(session.evidence.render_lines())
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- Audit log: `.weaver/audit/tools.jsonl`",
        ]
    )
    return "\n".join(lines) + "\n"


def _next_report_path(report_dir: Path, timestamp: datetime) -> Path:
    base = report_dir / f"{timestamp:%Y-%m-%d_%H%M%S}_session.md"
    if not base.exists():
        return base
    for index in range(2, 1000):
        candidate = report_dir / f"{timestamp:%Y-%m-%d_%H%M%S}_session_{index}.md"
        if not candidate.exists():
            return candidate
    return report_dir / f"{timestamp:%Y-%m-%d_%H%M%S}_{timestamp.microsecond}_session.md"


def _count_tool_results(messages: list[dict[str, Any]]) -> int:
    count = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            count += sum(1 for block in content if isinstance(block, dict) and block.get("type") == "tool_result")
    return count


def _render_recent_messages(messages: list[dict[str, Any]]) -> list[str]:
    if not messages:
        return ["- No messages recorded."]
    rendered: list[str] = []
    for message in messages:
        role = str(message.get("role") or "unknown")
        rendered.append(f"- **{role}**: {_message_preview(message)}")
    return rendered


def _message_preview(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return _single_line(content, 220)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                parts.append(f"tool_use:{block.get('name')}")
            elif block.get("type") == "tool_result":
                parts.append("tool_result")
        return _single_line(" | ".join(parts), 220)
    return "-"


def _single_line(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "…"
