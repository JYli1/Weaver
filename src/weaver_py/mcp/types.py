from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from weaver_py.config import McpServerConfig


@dataclass(frozen=True)
class McpToolSpec:
    server: str
    name: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class McpServerState:
    name: str
    config: McpServerConfig
    status: str = "pending"
    tools: list[McpToolSpec] = field(default_factory=list)
    last_error: str = ""
