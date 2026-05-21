from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant"]
Message = dict[str, Any]


@dataclass
class Conversation:
    messages: list[Message] = field(default_factory=list)

    def add_user_text(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant_blocks(self, content: list[Any]) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_results(self, results: list[dict[str, Any]]) -> None:
        self.messages.append({"role": "user", "content": results})

    def clear(self) -> None:
        self.messages.clear()
