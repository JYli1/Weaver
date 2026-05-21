from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    output: str
    exit_code: int
    timed_out: bool = False
    is_error: bool = False


class BaseTool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @abstractmethod
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        raise NotImplementedError
