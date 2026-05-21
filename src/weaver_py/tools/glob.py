from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult


class GlobTool(BaseTool):
    name = "Glob"
    description = "Find files by glob pattern."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern such as **/*.py."},
            "path": {"type": "string", "description": "Directory to search from."},
        },
        "required": ["pattern"],
    }

    async def execute(self, input: dict[str, object]) -> ToolResult:
        pattern = input.get("pattern")
        if not isinstance(pattern, str):
            return ToolResult("pattern must be a string", 1, is_error=True)
        root = Path(str(input.get("path") or ".")).expanduser()
        if not root.exists() or not root.is_dir():
            return ToolResult(f"Directory not found: {root}", 1, is_error=True)
        try:
            matches = [p for p in root.glob(pattern) if p.is_file()]
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError as exc:
            return ToolResult(f"Glob failed: {exc}", 1, is_error=True)
        return ToolResult("\n".join(str(p) for p in matches[:500]) or "No files found", 0)
