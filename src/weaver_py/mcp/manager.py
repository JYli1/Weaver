from __future__ import annotations

from weaver_py.config import McpServerConfig

from .client import McpClient
from .types import McpServerState, McpToolSpec


class McpManager:
    def __init__(self, configs: dict[str, McpServerConfig]):
        self.configs = configs
        self.clients: dict[str, McpClient] = {}
        self.states: dict[str, McpServerState] = {name: McpServerState(name=name, config=config) for name, config in configs.items()}

    async def initialize(self) -> None:
        for name, config in self.configs.items():
            state = self.states[name]
            client = McpClient(name, config)
            self.clients[name] = client
            try:
                await client.connect()
                state.tools = await client.list_tools()
                state.status = "connected"
                state.last_error = ""
            except Exception as exc:
                state.status = "failed"
                state.last_error = str(exc)
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def reload(self) -> None:
        await self.shutdown()
        self.clients.clear()
        self.states = {name: McpServerState(name=name, config=config) for name, config in self.configs.items()}
        await self.initialize()

    async def shutdown(self) -> None:
        for client in list(self.clients.values()):
            await client.disconnect()

    def all_tools(self) -> list[McpToolSpec]:
        tools: list[McpToolSpec] = []
        for state in self.states.values():
            tools.extend(state.tools)
        return tools

    def state_lines(self) -> list[str]:
        if not self.states:
            return ["MCP servers:\n  none — configure project .mcp.json or run /init migrate-claude"]
        lines = ["MCP servers:"]
        for state in self.states.values():
            suffix = f" tools={len(state.tools)}"
            if state.last_error:
                suffix += f" error={state.last_error}"
            lines.append(f"  {state.name} {state.status}{suffix}")
        return lines

    def server_detail(self, name: str) -> str:
        state = self.states.get(name)
        if state is None:
            return f"未知 MCP 服务器：{name}"
        lines = [f"MCP server: {state.name}", f"status={state.status}"]
        if state.last_error:
            lines.append(f"error={state.last_error}")
        if state.tools:
            lines.append("tools:")
            for tool in state.tools:
                lines.append(f"  {tool.tool_name} — {tool.description}")
        else:
            lines.append("tools: none")
        return "\n".join(lines)
