from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult


class ReadTool(BaseTool):
    name = "Read"
    description = "Read a UTF-8 text file from the local filesystem."
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to read."},
            "offset": {"type": "integer", "description": "Zero-based line offset."},
            "limit": {"type": "integer", "description": "Maximum number of lines to return."},
        },
        "required": ["file_path"],
    }

    async def execute(self, input: dict[str, object]) -> ToolResult:
        raw_path = input.get("file_path")
        if not isinstance(raw_path, str):
            return ToolResult("file_path must be a string", 1, is_error=True)
        path = Path(raw_path).expanduser()
        if not path.exists() or not path.is_file():
            return ToolResult(f"File not found: {path}", 1, is_error=True)
        offset = int(input.get("offset") or 0)
        limit_value = input.get("limit")
        limit = int(limit_value) if limit_value is not None else 2000
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return ToolResult(f"Failed to read {path}: {exc}", 1, is_error=True)
        selected = lines[offset : offset + limit]
        rendered = "\n".join(f"{idx}\t{line}" for idx, line in enumerate(selected, start=offset + 1))
        return ToolResult(rendered, 0)
