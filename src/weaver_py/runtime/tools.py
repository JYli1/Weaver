from __future__ import annotations

import sys
from pathlib import Path

from weaver_py.tools import BashTool, EditTool, GlobTool, GrepTool, PowerShellTool, ReadTool, ToolRegistry, UpdatePhaseTool, WriteTool


def build_default_registry(root: Path | None = None, audit_name: str = "tools.jsonl") -> ToolRegistry:
    audit_path = (root / ".weaver" / "audit" / audit_name) if root else None
    shell_tools = [PowerShellTool(), BashTool()] if sys.platform == "win32" else [BashTool()]
    return ToolRegistry(
        [UpdatePhaseTool(), ReadTool(), WriteTool(), EditTool(), GlobTool(), GrepTool(), *shell_tools],
        audit_path=audit_path,
    )
