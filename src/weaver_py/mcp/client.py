from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from weaver_py.config import McpServerConfig

from .types import McpToolSpec


class McpClient:
    def __init__(self, name: str, config: McpServerConfig, timeout: float = 30.0):
        self.name = name
        self.config = config
        self.timeout = timeout
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self.connected = False
        self.last_error = ""

    async def connect(self) -> None:
        env = {**os.environ, **self.config.env}
        self.process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "weaver", "version": "0.1.0"},
            },
        )
        await self.notify("notifications/initialized", {})
        self.connected = True

    async def list_tools(self) -> list[McpToolSpec]:
        result = await self.request("tools/list", {})
        tools = result.get("tools") if isinstance(result, dict) else []
        specs: list[McpToolSpec] = []
        for item in tools or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if not name:
                continue
            specs.append(
                McpToolSpec(
                    server=self.name,
                    name=name,
                    tool_name=f"mcp__{sanitize_tool_name(self.name)}__{sanitize_tool_name(name)}",
                    description=str(item.get("description") or name),
                    input_schema=_schema(item.get("inputSchema")),
                )
            )
        return specs

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self.request("tools/call", {"name": name, "arguments": arguments})
        if isinstance(result, dict) and isinstance(result.get("content"), list):
            return "\n".join(_content_to_text(item) for item in result["content"])
        return json.dumps(result, ensure_ascii=False)

    async def request(self, method: str, params: dict[str, Any]) -> Any:
        process = self._process()
        self._request_id += 1
        request_id = self._request_id
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        assert process.stdin is not None
        process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        await process.stdin.drain()
        while True:
            # MCP servers may emit notifications or responses for other request IDs on the same stdout stream.
            line = await asyncio.wait_for(self._readline(), timeout=self.timeout)
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") != request_id:
                continue
            if message.get("error"):
                error = message["error"]
                detail = error.get("message") if isinstance(error, dict) else str(error)
                raise RuntimeError(f"MCP error from {self.name}: {detail}")
            return message.get("result") or {}

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        process = self._process()
        assert process.stdin is not None
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        await process.stdin.drain()

    async def disconnect(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=2)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()
        self.connected = False
        self.process = None

    def _process(self) -> asyncio.subprocess.Process:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError(f"MCP server {self.name} is not connected")
        return self.process

    async def _readline(self) -> str:
        process = self._process()
        assert process.stdout is not None
        data = await process.stdout.readline()
        if data == b"":
            raise RuntimeError(f"MCP server {self.name} disconnected")
        return data.decode("utf-8", errors="replace")


def sanitize_tool_name(value: str) -> str:
    # Tool names become mcp__server__tool identifiers, so each segment must be schema-safe.
    cleaned = "".join(char if char.isalnum() else "_" for char in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "mcp_tool"


def _schema(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"type": "object", "properties": {}}


def _content_to_text(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("type") == "text":
            return str(value.get("text") or "")
        return json.dumps(value, ensure_ascii=False)
    return str(value)
