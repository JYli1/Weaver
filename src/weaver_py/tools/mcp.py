from __future__ import annotations

from typing import Any

from weaver_py.mcp import McpClient, McpToolSpec

from .base import BaseTool, ToolResult


class McpToolAdapter(BaseTool):
    def __init__(self, spec: McpToolSpec, client: McpClient):
        self.spec = spec
        self.client = client
        self.name = spec.tool_name
        self.description = f"[MCP:{spec.server}] {spec.description}"
        self.input_schema = spec.input_schema

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            output = await self.client.call_tool(self.spec.name, input)
        except Exception as exc:
            return ToolResult(f"MCP error: {exc}", 1, is_error=True)
        return ToolResult(output, 0)
