from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    description: str = ""
    disabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class SimpleTerminalSelector:
    async def choose(self, title: str, choices: list[Choice]) -> Choice | None:
        enabled = [choice for choice in choices if not choice.disabled]
        if not enabled:
            return None
        print(f"\n{title}")
        for index, choice in enumerate(enabled, start=1):
            suffix = f"  {choice.description}" if choice.description else ""
            print(f"  {index}. {choice.label}{suffix}")
        raw = await asyncio.to_thread(input, "Select> ")
        raw = raw.strip()
        if not raw:
            return None
        try:
            selected = int(raw)
        except ValueError:
            for choice in enabled:
                if raw == choice.id or raw == choice.label:
                    return choice
            return None
        if selected < 1 or selected > len(enabled):
            return None
        return enabled[selected - 1]
