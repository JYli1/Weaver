from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult


class WriteTool(BaseTool):
    name = "Write"
    description = "Write UTF-8 text content to a local file, creating or overwriting that file."
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to write."},
            "content": {"type": "string", "description": "Full text content to write."},
        },
        "required": ["file_path", "content"],
    }

    async def execute(self, input: dict[str, object]) -> ToolResult:
        raw_path = input.get("file_path")
        content = input.get("content")
        if not isinstance(raw_path, str):
            return ToolResult("file_path must be a string", 1, is_error=True)
        if not isinstance(content, str):
            return ToolResult("content must be a string", 1, is_error=True)

        path = Path(raw_path).expanduser()
        if path.exists() and path.is_dir():
            return ToolResult(f"Cannot write file because path is a directory: {path}", 1, is_error=True)
        if not path.parent.exists():
            return ToolResult(f"Parent directory does not exist: {path.parent}", 1, is_error=True)

        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(f"Failed to write {path}: {exc}", 1, is_error=True)
        return ToolResult(f"Wrote {len(content)} characters to {path}", 0)
