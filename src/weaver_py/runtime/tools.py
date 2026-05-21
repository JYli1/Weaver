from __future__ import annotations

from pathlib import Path

from weaver_py.tools import BashTool, EditTool, GlobTool, GrepTool, ReadTool, ToolRegistry, UpdatePhaseTool, WriteTool


def build_default_registry(root: Path | None = None, audit_name: str = "tools.jsonl") -> ToolRegistry:
    audit_path = (root / ".weaver" / "audit" / audit_name) if root else None
    return ToolRegistry(
        [UpdatePhaseTool(), ReadTool(), WriteTool(), EditTool(), GlobTool(), GrepTool(), BashTool()],
        audit_path=audit_path,
    )
