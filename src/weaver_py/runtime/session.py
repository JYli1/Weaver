from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from weaver_py.agent import AgentEngine
from weaver_py.agent.events import AgentEvent
from weaver_py.config import WeaverConfig, load_config
from weaver_py.mcp import McpManager
from weaver_py.skills import LoadedSkill, SkillLoader
from weaver_py.tools import McpToolAdapter, SkillTool, ToolRegistry

from .tools import build_default_registry

EventHandler = Callable[[AgentEvent], Awaitable[None] | None]


class WeaverSession:
    def __init__(
        self,
        root: Path,
        event_handler: EventHandler | None = None,
        config: WeaverConfig | None = None,
        registry: ToolRegistry | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self.root = root
        self.config = config or load_config(root)
        self.session_id = uuid4().hex
        self.skill_warnings: list[str] = []
        self.skills: list[LoadedSkill] = []
        self.mcp = McpManager(self.config.mcp_servers)
        self._runtime_ready = False
        self.registry = registry or build_default_registry(root)
        self.reload_skills()
        self.started_at = datetime.now()
        self.input_tokens = 0
        self.output_tokens = 0
        self.current_phase = "general"
        self.phase_confidence = 0.0
        self.phase_reason = ""
        self.current_task = ""
        self.tool_events: list[dict[str, Any]] = []
        self._external_event_handler = event_handler
        self.engine = AgentEngine(
            config=self.config,
            tools=self.registry,
            event_handler=self.handle_agent_event,
            root=root,
            max_tokens=max_tokens,
            skills=self.skills,
            project_context=self.project_context(),
        )

    def reload_skills(self) -> None:
        loader = SkillLoader(self.root)
        self.skills = loader.load_all()
        self.skill_warnings = loader.warnings
        self.registry.register(SkillTool(self.skills, session_id=self.session_id))
        if hasattr(self, "engine"):
            self.engine.skills = self.skills
            self.engine.project_context = self.project_context()

    def project_context(self, limit: int = 6000) -> str:
        path = self.root / "CLAUDE.md"
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return ""
        if len(text) <= limit:
            return text
        return text[:limit] + "\n\n[CLAUDE.md truncated; use Read to inspect the full file.]"

    @property
    def conversation(self) -> Any:
        return self.engine.conversation

    async def ensure_runtime_ready(self) -> None:
        if self._runtime_ready:
            return
        await self.mcp.initialize()
        self._register_mcp_tools()
        self._runtime_ready = True

    async def reload_mcp(self) -> None:
        await self.mcp.reload()
        self._register_mcp_tools()
        self._runtime_ready = True

    def _register_mcp_tools(self) -> None:
        for spec in self.mcp.all_tools():
            client = self.mcp.clients.get(spec.server)
            if client is not None and client.connected:
                self.registry.register(McpToolAdapter(spec, client))

    async def ask(self, prompt: str) -> str:
        await self.ensure_runtime_ready()
        self.current_task = prompt[:60]
        return await self.engine.ask(prompt)

    def clear(self) -> None:
        self.engine.conversation.clear()
        self.input_tokens = 0
        self.output_tokens = 0
        self.current_phase = "general"
        self.phase_confidence = 0.0
        self.phase_reason = ""
        self.current_task = ""
        self.tool_events.clear()

    async def handle_agent_event(self, event: AgentEvent) -> None:
        self.update_from_event(event)
        if self._external_event_handler is None:
            return
        result = self._external_event_handler(event)
        if hasattr(result, "__await__"):
            await result

    def update_from_event(self, event: AgentEvent) -> None:
        if event.type == "token_update":
            self.input_tokens = int(event.data.get("input_tokens") or self.input_tokens)
            self.output_tokens = int(event.data.get("output_tokens") or self.output_tokens)
        elif event.type == "phase_update":
            self.current_phase = str(event.data.get("phase") or "general")
            try:
                self.phase_confidence = float(event.data.get("confidence") or 0.0)
            except (TypeError, ValueError):
                self.phase_confidence = 0.0
            self.phase_reason = str(event.data.get("reason") or "")
            self.current_task = str(event.data.get("current_task") or "")
        elif event.type == "tool_start":
            name = str(event.data.get("name") or "tool")
            self.current_task = name
            self.tool_events.append({"type": "start", "name": name, "input": event.data.get("input")})
        elif event.type in {"tool_result", "tool_error"}:
            self.tool_events.append(
                {
                    "type": event.type,
                    "name": event.data.get("name"),
                    "exit_code": event.data.get("exit_code"),
                    "output": str(event.data.get("output") or "")[:500],
                }
            )

    def status_plain(self) -> str:
        message_count = len(self.engine.conversation.messages)
        total_tokens = self.input_tokens + self.output_tokens
        tools = ", ".join(schema["name"] for schema in self.registry.schemas())
        mcp_connected = sum(1 for state in self.mcp.states.values() if state.status == "connected")
        mcp_failed = sum(1 for state in self.mcp.states.values() if state.status == "failed")
        return (
            f"phase={self.current_phase} confidence={self.phase_confidence:.2f} "
            f"model={self.config.model} backend={self.config.backend.type}\n"
            f"root={self.root}\n"
            f"messages={message_count} tokens={total_tokens} current_task={self.current_task or '-'} "
            f"reason={self.phase_reason or '-'}\n"
            f"skills={len(self.skills)} mcp_servers={len(self.mcp.states)} connected={mcp_connected} failed={mcp_failed}\n"
            f"tools={tools} audit=.weaver/audit/tools.jsonl"
        )

    def report_dir(self) -> Path:
        configured = self.config.reports_dir.strip() if self.config.reports_dir else ""
        if not configured or configured == "~/.weaver/reports/":
            return self.root / ".weaver" / "reports"
        path = Path(configured).expanduser()
        if path.is_absolute():
            return path
        return self.root / path

    def has_interaction(self) -> bool:
        return bool(self.engine.conversation.messages)
