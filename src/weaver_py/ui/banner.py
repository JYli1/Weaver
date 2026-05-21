from __future__ import annotations

from pathlib import Path
from typing import Any


def _fit(text: str, width: int) -> str:
    if len(text) <= width:
        return text.ljust(width)
    if width <= 1:
        return "…"
    return text[: width - 1] + "…"


def _center(text: str, width: int) -> str:
    if len(text) >= width:
        return _fit(text, width)
    left = (width - len(text)) // 2
    return " " * left + text + " " * (width - len(text) - left)


def render_banner(config: Any, root: Path, unicode: bool = True, width: int = 96) -> str:
    model = getattr(config, "model", "unknown")
    backend = getattr(getattr(config, "backend", None), "type", "unknown")
    separator = "·" if unicode else "-"
    total_width = max(72, min(width, 126))
    left_width = 30 if total_width < 100 else 34
    right_width = total_width - left_width - 7
    title = " Weaver v0.1.0 "

    if unicode:
        top = "╭───" + title + "─" * (total_width - len(title) - 5) + "╮"
        bottom = "╰" + "─" * (total_width - 2) + "╯"
        side = "│"
        divider = "│"
        rule = "─" * right_width
        logo = ["╲╱╲╱╲╱", " WEAVER ", "╱╲╱╲╱╲"]
    else:
        top = "+---" + title + "-" * (total_width - len(title) - 5) + "+"
        bottom = "+" + "-" * (total_width - 2) + "+"
        side = "|"
        divider = "|"
        rule = "-" * right_width
        logo = ["\\/\\/\\/", " WEAVER ", "/\\/\\/\\"]

    left = [
        "",
        "Welcome back!",
        "",
        *logo,
        "",
        f"{model} {separator} {backend}",
        str(root),
    ]
    right = [
        "Tips for getting started",
        "Run /init to create or refresh project instructions",
        rule,
        "What's ready",
        "CLI-first runtime with slash commands, tools, Skills and MCP",
        "Session reports are saved on /exit",
        "Use /help for commands, /status for runtime state",
        "Use /mcp and /skills to inspect integrations",
    ]

    rows = max(len(left), len(right))
    body: list[str] = []
    for index in range(rows):
        left_text = _center(left[index], left_width) if index < len(left) else " " * left_width
        right_text = _fit(right[index], right_width) if index < len(right) else " " * right_width
        body.append(f"{side} {left_text} {divider} {right_text} {side}")
    return "\n".join([top, *body, bottom])
