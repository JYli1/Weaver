from __future__ import annotations

from pathlib import Path

from .base import BaseTool, ToolResult


class EditTool(BaseTool):
    name = "Edit"
    description = "Edit a UTF-8 text file by replacing an exact string with new text."
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to edit."},
            "old_string": {"type": "string", "description": "Exact text to replace."},
            "new_string": {"type": "string", "description": "Replacement text."},
            "replace_all": {"type": "boolean", "description": "Replace every occurrence instead of requiring one unique match."},
        },
        "required": ["file_path", "old_string", "new_string"],
    }

    async def execute(self, input: dict[str, object]) -> ToolResult:
        raw_path = input.get("file_path")
        old_string = input.get("old_string")
        new_string = input.get("new_string")
        replace_all = bool(input.get("replace_all") or False)
        if not isinstance(raw_path, str):
            return ToolResult("file_path must be a string", 1, is_error=True)
        if not isinstance(old_string, str) or not isinstance(new_string, str):
            return ToolResult("old_string and new_string must be strings", 1, is_error=True)
        if old_string == "":
            return ToolResult("old_string must not be empty", 1, is_error=True)
        if old_string == new_string:
            return ToolResult("old_string and new_string must be different", 1, is_error=True)

        path = Path(raw_path).expanduser()
        if not path.exists() or not path.is_file():
            return ToolResult(f"File not found: {path}", 1, is_error=True)

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(f"Failed to read {path}: {exc}", 1, is_error=True)

        count = content.count(old_string)
        if count == 0:
            return ToolResult("old_string was not found", 1, is_error=True)
        if not replace_all and count != 1:
            return ToolResult(f"old_string is not unique: found {count} matches", 1, is_error=True)

        updated = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)
        try:
            path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            return ToolResult(f"Failed to write {path}: {exc}", 1, is_error=True)
        replacements = count if replace_all else 1
        return ToolResult(f"Edited {path}: replaced {replacements} occurrence(s)", 0)
