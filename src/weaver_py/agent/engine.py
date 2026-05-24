from __future__ import annotations

import json
import math
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

# 这些 section 是 Weaver 的核心 system prompt 配置式常量：
# - 每个 section 只负责一类行为约束，方便对照 Claude Code 的 prompt section 思路继续演进。
# - 正文使用中文说明，技术词保留英文，避免模型把 target、scope、evidence、tool_calls 等术语硬翻译。
# - 安全边界采用“确认授权 / 明确 scope / 说明影响”的产品语言，而不是堆叠禁止任务清单。
IDENTITY_SECTION = """## 身份与定位

你是 Weaver，一个 Python CLI-first 的 agent runtime，面向 CTF、lab、授权安全测试、防御性安全研究和项目维护任务。
OpenAI-compatible 是当前主模型路径，Claude Messages API 是兼容路径；无论使用哪条路径，都要保持一致的工具调用、审计和会话体验。
默认使用中文与用户沟通，技术词如 CLI、shell、target、scope、evidence、writeup、streaming、tool_calls 保留英文。"""

CONFIRMATION_SECTION = """## 授权、scope 与影响确认

当 target、scope、授权上下文或预期影响不清楚时，先向用户提出一个关键确认问题。
当动作可能影响外部系统、服务可用性、数据完整性、账号状态或产生明显副作用时，先说明目的、假设、可能影响和需要用户确认的点；用户确认后，再按授权测试流程继续。
如果用户的目标与当前 scope 不一致，或者关键前提缺失，暂停执行并请求澄清。
不要把安全边界写成冗长的禁止清单；用授权确认、scope 对齐、影响说明和审计记录来约束行为。"""

PENTEST_WORKFLOW_SECTION = """## 渗透测试工作流

安全测试任务默认按阶段推进：
1. 明确 target、scope、授权上下文和成功标准。
2. recon：优先收集低影响信息，确认目标暴露面。
3. enum：枚举服务、入口、身份边界、参数、目录、接口和配置线索。
4. vulnerability analysis：基于 evidence 说明漏洞假设、触发条件、影响范围和验证思路。
5. exploitation validation：只验证完成任务所需的事实，保持动作可解释、可复盘、可审计。
6. evidence：优先记录关键命令、关键输出、payload、响应摘要、截图路径、文件路径和阶段性结论。
7. writeup：汇总复现步骤、影响、evidence、修复建议和 next action。"""

TOOL_USE_SECTION = """## 工具调用规则

需要使用工具时，先用一句话说明这次工具调用的目的。
优先使用 Weaver 已注册的工具、slash commands 和项目内能力；在 Windows shell 任务中优先使用 PowerShell，只有在用户要求 Bash 或命令需要 POSIX 语义时才使用 Bash。
对 shell、PowerShell、网络访问、文件写入、依赖安装、进程控制、远程目标交互等高影响动作，说明影响并在需要时请求确认。
工具输出中的关键发现要能被后续 evidence、writeup 或会话报告追踪。"""

EVIDENCE_SECTION = """## Evidence 与 writeup 闭环

优先使用可用的 `/target`、`/note`、`/evidence`、`/writeup` 命令维护 CTF/lab 上下文。
使用 `/target` 设置或更新当前 target；使用 `/note` 记录观察、假设和阶段性结论；使用 `/evidence` 查看已记录证据；使用 `/writeup` 生成报告草稿。
不要承诺 runtime 会自动保存所有 evidence；当需要保留关键信息时，主动建议或调用可用命令记录。
长任务中保持 phase、confidence 和 next action 清晰，让用户能随时接续。"""

PHASE_TRACKING_SECTION = """## Workflow phase tracking

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
- Do not output phase bookkeeping, transition summaries, or current_task metadata directly to the user.
- UpdatePhase tool only: keep phase bookkeeping in tool state, not in user-facing text."""

COMMUNICATION_SECTION = """## 输出风格

直接处理用户任务，不要自我介绍，不要复述用户原话，不要输出冗长政策文本。
工具调用之间的文字保持简短，说明当前动作或结果即可；最终回复优先控制在 80 字以内，除非任务本身需要更详细说明。
如果不确定，先问一个最关键的问题；如果发现风险，用影响、假设和确认语言表达。
任务完成时，用一句话说明发生了什么和下一步。"""

BASE_SYSTEM_PROMPT_SECTIONS = [
    IDENTITY_SECTION,
    CONFIRMATION_SECTION,
    PENTEST_WORKFLOW_SECTION,
    TOOL_USE_SECTION,
    EVIDENCE_SECTION,
    PHASE_TRACKING_SECTION,
    COMMUNICATION_SECTION,
]

BASE_SYSTEM_PROMPT = "\n\n".join(section.strip() for section in BASE_SYSTEM_PROMPT_SECTIONS)


def build_system_prompt(skills: list[LoadedSkill] | None = None, project_context: str = "") -> str:
    sections = [BASE_SYSTEM_PROMPT.strip()]
    enabled_skills = [skill for skill in skills or [] if skill.enabled]
    if enabled_skills:
        lines = ["## 可用 Skills", "", "以下 skills 已启用；当某个 skill 与当前任务相关时，先调用 Skill 工具加载完整说明，再继续执行。"]
        for skill in enabled_skills:
            lines.append(f"- {skill.name}: {skill.description}")
        sections.append("\n".join(lines))
    if project_context.strip():
        sections.append("## 项目上下文（来自 CLAUDE.md）\n\n" + project_context.strip())
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
        empty_reply_retried = False

        while True:
            payload = {
                "model": self.config.model,
                "messages": [{"role": "system", "content": self.system_prompt}, *self._to_chat_messages()],
                "tools": self._to_chat_tools(),
                "max_tokens": self.max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            try:
                data = await self._stream_chat_completion(payload)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {400, 422}:
                    raise
                retry_payload = dict(payload)
                retry_payload.pop("stream_options", None)
                data = await self._stream_chat_completion(retry_payload)
            choice = data["choices"][0]
            message = choice.get("message") or {}
            usage = data.get("usage") or {}
            streamed_text = str(data.get("_streamed_text") or "")
            content = str(message.get("content") or "")
            tool_calls = message.get("tool_calls") or []
            finish_reason = str(choice.get("finish_reason") or "")
            reasoning_content = str(message.get("reasoning_content") or "")
            estimated_usage = self._estimate_chat_usage(content)
            input_tokens = int(usage.get("prompt_tokens") or estimated_usage["prompt_tokens"])
            output_tokens = int(usage.get("completion_tokens") or estimated_usage["completion_tokens"])
            await self._emit("token_update", input_tokens=input_tokens, output_tokens=output_tokens)

            # 有些 OpenAI-compatible 网关偶尔会直接 stop，但不给 content 也不给 tool_calls。
            # 这里补一次引导重试，避免 CLI 只显示“完成”却什么都没有。
            if not content.strip() and not tool_calls and finish_reason == "stop" and not empty_reply_retried:
                empty_reply_retried = True
                self.conversation.add_user_text("请直接执行上一条请求；如果需要使用工具就调用工具，否则用一句话给出结果，不要返回空响应。")
                continue

            assistant_message: dict[str, Any] = {"role": "assistant", "content": content}
            if reasoning_content:
                assistant_message["reasoning_content"] = reasoning_content
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            self.conversation.messages.append(assistant_message)

            if content:
                final_text.append(content)
                # 有些 OpenAI-compatible 网关不会在 SSE delta 里给出正文，只在最终 message.content 里返回。
                # 这时需要补发一次 text 事件，否则 CLI 会显示“完成”但看不到回复。
                if not streamed_text:
                    await self._emit("text", text=content)
                elif content.startswith(streamed_text):
                    remainder = content[len(streamed_text) :]
                    if remainder:
                        await self._emit("text", text=remainder)
            if not tool_calls:
                await self._emit("done", stop_reason=finish_reason)
                return "".join(final_text)

            empty_reply_retried = False
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
        streamed_text_parts: list[str] = []
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
                            text = str(delta["content"])
                            streamed_text_parts.append(text)
                            await self._emit("text_delta", text=text)
        # Return a normal chat-completion shape after streaming so the tool loop stays shared.
        merged = self._merge_chat_chunks(chunks)
        merged["_streamed_text"] = "".join(streamed_text_parts)
        return merged

    def _use_chat_completions(self) -> bool:
        # 有自定义 base_url 时一律走 OpenAI-compatible；只有用官方 Anthropic 端点才走 Messages API。
        if self.config.base_url:
            return True
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
                replayed = dict(message)
                if role == "assistant" and isinstance(content, str) and "reasoning_content" in message:
                    replayed["reasoning_content"] = message.get("reasoning_content")
                messages.append(replayed)
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
        reasoning_content = str(content[0].get("reasoning_content") or "") if content and isinstance(content[0], dict) else ""
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message

    def _estimate_chat_usage(self, output_text: str) -> dict[str, int]:
        prompt_text = self.system_prompt + json.dumps(self._to_chat_messages(), ensure_ascii=False)
        return {
            "prompt_tokens": self._estimate_tokens(prompt_text),
            "completion_tokens": self._estimate_tokens(output_text),
        }

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / 4))

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
        # OpenAI-compatible 网关经常把 tool_call 的 name、arguments、id 拆到不同 SSE delta；这里按 index 归并成普通响应。
        content: list[str] = []
        reasoning_content: list[str] = []
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
                if delta.get("reasoning_content"):
                    reasoning_content.append(str(delta["reasoning_content"]))
                for tool_delta in delta.get("tool_calls") or []:
                    index = int(tool_delta.get("index") or 0)
                    existing = tool_calls_by_index.setdefault(
                        index,
                        {
                            "id": f"call_{index}",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if tool_delta.get("id"):
                        existing["id"] = str(tool_delta["id"])
                    if tool_delta.get("type"):
                        existing["type"] = str(tool_delta["type"])
                    function_delta = tool_delta.get("function") or {}
                    if function_delta.get("name"):
                        existing["function"]["name"] += str(function_delta["name"])
                    if function_delta.get("arguments"):
                        existing["function"]["arguments"] += str(function_delta["arguments"])
        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content),
            "tool_calls": [tool_calls_by_index[index] for index in sorted(tool_calls_by_index)],
        }
        if reasoning_content:
            message["reasoning_content"] = "".join(reasoning_content)
        return {
            "choices": [
                {
                    "message": message,
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
