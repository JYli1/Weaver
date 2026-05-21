from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal[
    "status_change",
    "text",
    "text_delta",
    "tool_start",
    "tool_result",
    "tool_error",
    "token_update",
    "phase_update",
    "context_warning",
    "progress_saved",
    "done",
    "error",
]


@dataclass(frozen=True)
class AgentEvent:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
