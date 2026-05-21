from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
from anthropic import AsyncAnthropic

from weaver_py.config import WeaverConfig
from weaver_py.progress import ProgressTracker
from weaver_py.skills import LoadedSkill
from weaver_py.tools import ToolRegistry

from .conversation import Conversation
from .events import AgentEvent

EventHandler = Callable[[AgentEvent], Awaitable[None] | None]

BASE_SYSTEM_PROMPT = """You are Weaver, an authorized security testing and defensive research agent.
Use tools only within user-authorized scope. Do not perform destructive actions, DoS, detection evasion, credential abuse, or unauthorized mass scanning.

Workflow phase tracking:
- Keep Weaver's pentest workflow phase accurate using the UpdatePhase tool.
- Call UpdatePhase when the user's intent, your plan, or a tool result indicates the current phase.
- Phases are: general, recon, enum, exploit, post, report.
- Prefer general for normal coding, explanation, configuration, or project maintenance.
- Use recon for target discovery, port/network/host scanning, asset discovery, or external intelligence gathering.
- Use enum for service/web/directory/user/share enumeration and vulnerability discovery after targets are known.
- Use exploit only for authorized exploit validation or exploitation planning with explicit scope.
- Use post only for authorized post-exploitation analysis after a validated foothold.
- Use report for findings, evidence organization, summaries, and report generation.
- Include confidence, a short transition reason, and a concise current_task.
"""


def build_system_prompt(skills: list[LoadedSkill] | None = None, project_context: str = "") -> str:
    sections = [BASE_SYSTEM_PROMPT.strip()]
    enabled_skills = [skill for skill in skills or [] if skill.enabled]
    if enabled_skills:
        lines = ["Available skills:"]
        for skill in enabled_skills:
            lines.append(f"- {skill.name}: {skill.description}")
        lines.append("When a skill is relevant, call the Skill tool first to load its full instructions.")
        sections.append("\n".join(lines))
    if project_context.strip():
        sections.append("Project context from CLAUDE.md:\n" + project_context.strip())
    return "\n\n".join(sections)


class AgentEngine:
    def __init__(
        self,
        config: WeaverConfig,
        tools: ToolRegistry,
        event_handler: EventHandler | None = None,
        conversation: Conversation | None = None,
        max_tokens: int = 4096,
        root: Path | None = None,
        skills: list[LoadedSkill] | None = None,
        project_context: str = "",
    ) -> None:
        if not config.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required, or configure apiKey/apiKeyHelper in Weaver settings.")
        client_kwargs: dict[str, Any] = {"api_key": config.api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        self.client = AsyncAnthropic(**client_kwargs)
        self.config = config
        self.tools = tools
        self.event_handler = event_handler
        self.conversation = conversation or Conversation()
        self.max_tokens = max_tokens
        self.progress = ProgressTracker()
        self.root = root or Path.cwd()
        self.skills = skills or []
        self.project_context = project_context

    @property
    def system_prompt(self) -> str:
        return build_system_prompt(self.skills, self.project_context)

    async def ask(self, text: str) -> str:
        # Claude models use Messages API; gateway models use OpenAI-compatible chat completions.
        if self._use_chat_completions():
            return await self._ask_chat_completions(text)
        return await self._ask_anthropic_messages(text)

    async def _ask_anthropic_messages(self, text: str) -> str:
        self.conversation.add_user_text(text)
        await self._emit("status_change", phase="requesting")
        final_text: list[str] = []

        while True:
            message = await self.client.messages.create(
                model=self.config.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=self.conversation.messages,
                tools=self.tools.schemas(),
            )
            input_tokens = getattr(message.usage, "input_tokens", 0) if message.usage else 0
            output_tokens = getattr(message.usage, "output_tokens", 0) if message.usage else 0
            await self._emit("token_update", input_tokens=input_tokens, output_tokens=output_tokens)
            level = self.progress.level(input_tokens, output_tokens)
            if level != "ok":
                await self._emit("context_warning", level=level, input_tokens=input_tokens, output_tokens=output_tokens)
            note_path = self.progress.maybe_write_note(self.root, input_tokens, output_tokens)
            if note_path:
                await self._emit("progress_saved", path=str(note_path))

            content = [self._block_to_dict(block) for block in message.content]
            # Keep the full assistant blocks so tool_use IDs and future compaction blocks survive the next request.
            self.conversation.add_assistant_blocks(content)

            tool_uses = [block for block in content if block.get("type") == "tool_use"]
            for block in content:
                if block.get("type") == "text":
                    chunk = str(block.get("text") or "")
                    if chunk:
                        final_text.append(chunk)
                        await self._emit("text", text=chunk)

            if not tool_uses:
                await self._emit("done", stop_reason=message.stop_reason)
                return "".join(final_text)

            results: list[dict[str, Any]] = []
            for tool_use in tool_uses:
                tool_id = str(tool_use.get("id"))
                name = str(tool_use.get("name"))
                tool_input = tool_use.get("input")
                if not isinstance(tool_input, dict):
                    tool_input = {}
                await self._emit("tool_start", id=tool_id, name=name, input=tool_input)
                result = await self.tools.execute(name, tool_input)
                event_type = "tool_error" if result.is_error else "tool_result"
                await self._emit(event_type, id=tool_id, name=name, exit_code=result.exit_code, output=result.output)
                await self._emit_phase_update(name, result.output, result.is_error)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result.output,
                        "is_error": result.is_error,
                    }
                )
            self.conversation.add_tool_results(results)

    async def _ask_chat_completions(self, text: str) -> str:
        self.conversation.add_user_text(text)
        await self._emit("status_change", phase="requesting")
        final_text: list[str] = []

        while True:
            payload = {
                "model": self.config.model,
                "messages": [{"role": "system", "content": self.system_prompt}, *self._to_chat_messages()],
                "tools": self._to_chat_tools(),
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            data = await self._stream_chat_completion(payload)
            choice = data["choices"][0]
            message = choice.get("message") or {}
            usage = data.get("usage") or {}
            input_tokens = int(usage.get("prompt_tokens") or 0)
            output_tokens = int(usage.get("completion_tokens") or 0)
            await self._emit("token_update", input_tokens=input_tokens, output_tokens=output_tokens)

            content = str(message.get("content") or "")
            tool_calls = message.get("tool_calls") or []
            assistant_message: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            self.conversation.messages.append(assistant_message)

            if content:
                final_text.append(content)
            if not tool_calls:
                await self._emit("done", stop_reason=choice.get("finish_reason"))
                return "".join(final_text)

            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                name = str(function.get("name") or "")
                raw_arguments = function.get("arguments") or "{}"
                try:
                    tool_input = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                except json.JSONDecodeError:
                    tool_input = {}
                if not isinstance(tool_input, dict):
                    tool_input = {}
                tool_id = str(tool_call.get("id") or name)
                await self._emit("tool_start", id=tool_id, name=name, input=tool_input)
                result = await self.tools.execute(name, tool_input)
                event_type = "tool_error" if result.is_error else "tool_result"
                await self._emit(event_type, id=tool_id, name=name, exit_code=result.exit_code, output=result.output)
                await self._emit_phase_update(name, result.output, result.is_error)
                self.conversation.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": result.output,
                    }
                )

    async def _stream_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        chunks: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            async with client.stream(
                "POST",
                self.config.base_url.rstrip("/") + "/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        continue
                    chunk = json.loads(data)
                    chunks.append(chunk)
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            await self._emit("text_delta", text=str(delta["content"]))
        # Return a normal chat-completion shape after streaming so the tool loop stays shared.
        return self._merge_chat_chunks(chunks)

    def _use_chat_completions(self) -> bool:
        return not self.config.model.startswith("claude-")

    def _to_chat_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["input_schema"],
                },
            }
            for schema in self.tools.schemas()
        ]

    def _to_chat_messages(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for message in self.conversation.messages:
            role = message.get("role")
            content = message.get("content")
            if role == "user" and isinstance(content, list):
                messages.extend(self._tool_results_to_chat_messages(content))
            elif role == "assistant" and isinstance(content, list):
                messages.append(self._assistant_blocks_to_chat_message(content))
            else:
                messages.append(message)
        return messages

    def _tool_results_to_chat_messages(self, content: list[Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(block.get("tool_use_id")),
                        "content": str(block.get("content") or ""),
                    }
                )
        return results

    def _assistant_blocks_to_chat_message(self, content: list[Any]) -> dict[str, Any]:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_parts.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": str(block.get("id")),
                        "type": "function",
                        "function": {
                            "name": str(block.get("name")),
                            "arguments": json.dumps(block.get("input") or {}),
                        },
                    }
                )
        message: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts)}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message

    def _parse_chat_response(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("data:"):
            chunks: list[dict[str, Any]] = []
            for line in stripped.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line.removeprefix("data:").strip()
                if payload == "[DONE]":
                    continue
                chunks.append(json.loads(payload))
            return self._merge_chat_chunks(chunks)
        return json.loads(stripped)

    def _merge_chat_chunks(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        # Tool call names and JSON arguments can arrive split across multiple SSE deltas.
        content: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage: dict[str, Any] = {}
        for chunk in chunks:
            if chunk.get("usage"):
                usage = chunk["usage"]
            for choice in chunk.get("choices") or []:
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    content.append(str(delta["content"]))
                for tool_delta in delta.get("tool_calls") or []:
                    index = int(tool_delta.get("index") or 0)
                    existing = tool_calls_by_index.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                    if tool_delta.get("id"):
                        existing["id"] = tool_delta["id"]
                    function_delta = tool_delta.get("function") or {}
                    if function_delta.get("name"):
                        existing["function"]["name"] += function_delta["name"]
                    if function_delta.get("arguments"):
                        existing["function"]["arguments"] += function_delta["arguments"]
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "".join(content),
                        "tool_calls": list(tool_calls_by_index.values()),
                    },
                    "finish_reason": finish_reason,
                }
            ],
            "usage": usage,
        }

    async def _emit_phase_update(self, tool_name: str, output: str, is_error: bool) -> None:
        if tool_name != "UpdatePhase" or is_error:
            return
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        await self._emit(
            "phase_update",
            phase=data.get("phase", "general"),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason", ""),
            current_task=data.get("current_task", ""),
        )

    async def _emit(self, event_type: str, **data: Any) -> None:
        if self.event_handler is None:
            return
        result = self.event_handler(AgentEvent(type=event_type, data=data))
        if hasattr(result, "__await__"):
            await result

    def _block_to_dict(self, block: Any) -> dict[str, Any]:
        # Anthropic SDK objects may be Pydantic v1/v2 models depending on the installed version.
        if isinstance(block, dict):
            return block
        if hasattr(block, "model_dump"):
            return block.model_dump(exclude_none=True)
        if hasattr(block, "dict"):
            return block.dict(exclude_none=True)
        return json.loads(json.dumps(block, default=lambda value: getattr(value, "__dict__", str(value))))
