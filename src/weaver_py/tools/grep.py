from __future__ import annotations

import asyncio
from pathlib import Path

from .base import BaseTool, ToolResult


class GrepTool(BaseTool):
    name = "Grep"
    description = "Search file contents with ripgrep."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression to search for."},
            "path": {"type": "string", "description": "File or directory to search."},
            "glob": {"type": "string", "description": "Optional file glob filter."},
            "output_mode": {"type": "string", "enum": ["content", "files_with_matches", "count"]},
            "head_limit": {"type": "integer", "description": "Maximum output lines."},
        },
        "required": ["pattern"],
    }

    async def execute(self, input: dict[str, object]) -> ToolResult:
        pattern = input.get("pattern")
        if not isinstance(pattern, str):
            return ToolResult("pattern must be a string", 1, is_error=True)
        path = str(input.get("path") or ".")
        output_mode = str(input.get("output_mode") or "files_with_matches")
        head_limit = int(input.get("head_limit") or 250)
        cmd = ["rg", "--line-number"]
        if output_mode == "files_with_matches":
            cmd.append("--files-with-matches")
        elif output_mode == "count":
            cmd.append("--count")
        glob = input.get("glob")
        if isinstance(glob, str):
            cmd.extend(["--glob", glob])
        cmd.extend([pattern, path])
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except FileNotFoundError:
            return await self._fallback(pattern, Path(path), head_limit)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult("grep timed out", 1, timed_out=True, is_error=True)
        output = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace")
        if proc.returncode not in (0, 1):
            return ToolResult(err or output, proc.returncode or 1, is_error=True)
        lines = output.splitlines()[:head_limit]
        return ToolResult("\n".join(lines) or "No matches found", proc.returncode or 0)

    async def _fallback(self, pattern: str, root: Path, head_limit: int) -> ToolResult:
        import re

        regex = re.compile(pattern)
        matches: list[str] = []
        files = [root] if root.is_file() else root.rglob("*")
        for file in files:
            if not file.is_file():
                continue
            try:
                for number, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                    if regex.search(line):
                        matches.append(f"{file}:{number}:{line}")
                        if len(matches) >= head_limit:
                            return ToolResult("\n".join(matches), 0)
            except OSError:
                continue
        return ToolResult("\n".join(matches) or "No matches found", 0)
