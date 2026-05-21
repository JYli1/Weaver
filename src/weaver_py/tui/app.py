from __future__ import annotations

import time
from pathlib import Path

from rich.markup import escape
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, RichLog, Static

from weaver_py.agent.events import AgentEvent
from weaver_py.config import WeaverConfig
from weaver_py.runtime import WeaverSession, complete_commands, handle_command
from weaver_py.tui.theme import (
    CONTEXT_MAX_TOKENS,
    PALETTE,
    PHASE_CLASS_NAMES,
    PHASE_LABELS,
    PHASE_STYLES,
    detect_phase,
    format_tokens,
    token_style,
)



class WeaverTuiApp(App[None]):
    CSS = """
    Screen {
        background: #0B1020;
        color: #E5E7EB;
    }

    #layout {
        height: 100%;
        padding: 0 1;
    }

    #status {
        height: 4;
        border: solid #334155;
        padding: 0 1;
        color: #94A3B8;
        background: #111827;
    }

    #body {
        height: 1fr;
        margin: 1 0 0 0;
    }

    #messages {
        width: 2fr;
        height: 100%;
        border: solid #334155;
        padding: 0 1;
        background: #0F172A;
    }

    .message {
        margin: 0 0 1 0;
    }

    .system-message {
        color: #94A3B8;
    }

    .error-message {
        color: #F87171;
    }

    #tools {
        width: 1fr;
        height: 100%;
        margin: 0 0 0 1;
        border: solid #334155;
        padding: 0 1;
        color: #94A3B8;
        background: #0F172A;
    }

    #statusbar {
        height: 3;
        margin: 1 0 0 0;
        border: solid #334155;
        padding: 0 1;
        color: #94A3B8;
        background: #111827;
    }

    #command-menu {
        height: auto;
        max-height: 7;
        margin: 1 0 0 0;
        border: solid #334155;
        padding: 0 2;
        color: #94A3B8;
        background: #111827;
        display: none;
    }

    #command-menu.visible {
        display: block;
    }

    #input {
        height: 3;
        border: round #334155;
        padding: 0 1;
        color: #E5E7EB;
        background: #0B1020;
    }

    #input.phase-recon {
        border: round #60A5FA;
    }

    #input.phase-enum {
        border: round #38BDF8;
    }

    #input.phase-exploit {
        border: round #F87171;
    }

    #input.phase-post {
        border: round #64748B;
    }

    #input.phase-report {
        border: round #60A5FA;
    }

    #input.phase-general {
        border: round #334155;
    }

    #input:disabled {
        border: round #334155;
        color: #94A3B8;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.config: WeaverConfig | None = None
        self.session: WeaverSession | None = None
        self.engine = None
        self.busy = False
        self.current_phase = "general"
        self.phase_confidence = 0.0
        self.phase_reason = ""
        self.current_task = ""
        self.input_tokens = 0
        self.output_tokens = 0
        self._current_assistant: list[str] = []
        self._assistant_widget: Static | None = None
        self._run_started_at: float | None = None
        self._timer = None
        self._menu_index = 0
        self._filtered_commands: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="layout"):
            yield Static("Weaver Python TUI starting...", id="status")
            with Horizontal(id="body"):
                yield VerticalScroll(id="messages")
                yield RichLog(id="tools", wrap=True, markup=True, highlight=True)
            yield Static("[通用] idle │ 0 tokens │ 00:00", id="statusbar")
            yield Static("", id="command-menu")
            yield Input(placeholder="weaver> 输入任务或 /help", id="input", classes="phase-general")

    async def on_mount(self) -> None:
        tools = self.query_one("#tools", RichLog)
        try:
            self.session = WeaverSession(self.root, event_handler=self.handle_agent_event)
            self.config = self.session.config
            self.engine = self.session.engine
        except Exception as exc:
            await self._add_message("error", f"启动失败：{exc}")
            self.query_one("#input", Input).disabled = True
            return
        await self._add_message("system", "Weaver 已启动")
        await self._add_message("system", "输入任务后按回车。常用命令：/status /clear /report /help /exit")
        tools.write(f"[{PALETTE['text']}]工具[/{PALETTE['text']}]")
        tools.write(f"[{PALETTE['muted']}]工具执行摘要会显示在这里。[/{PALETTE['muted']}]")
        self._update_chrome("ready")
        self._timer = self.set_interval(1.0, self._tick)
        self.query_one("#input", Input).focus()

    def _tick(self) -> None:
        if self.busy:
            self._update_chrome("running")

    async def on_input_changed(self, event: Input.Changed) -> None:
        if self.busy:
            return
        self._update_command_menu(event.value)

    async def on_key(self, event: events.Key) -> None:
        if self.busy or not self._filtered_commands:
            return
        if event.key == "up":
            self._menu_index = (self._menu_index - 1) % len(self._filtered_commands)
            self._render_command_menu()
            event.stop()
        elif event.key == "down":
            self._menu_index = (self._menu_index + 1) % len(self._filtered_commands)
            self._render_command_menu()
            event.stop()
        elif event.key == "tab":
            command, _ = self._filtered_commands[self._menu_index]
            self.query_one("#input", Input).value = command
            self._update_command_menu(command)
            event.stop()
        elif event.key == "escape":
            self.query_one("#input", Input).value = ""
            self._hide_command_menu()
            event.stop()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        event.input.value = ""
        self._hide_command_menu()
        if not prompt or self.busy:
            return
        if await self._handle_slash_command(prompt):
            return
        self.busy = True
        event.input.disabled = True
        self.current_phase = detect_phase(prompt)
        self.current_task = prompt[:60]
        self._current_assistant = []
        self._assistant_widget = None
        self._run_started_at = time.monotonic()
        await self._add_message("user", prompt)
        self._update_chrome("running")
        self.run_worker(self._run_prompt(prompt), exclusive=True, thread=False)

    async def _run_prompt(self, prompt: str) -> None:
        try:
            if self.session is None:
                raise RuntimeError("WeaverSession is not initialized")
            await self.session.ask(prompt)
        except Exception as exc:
            await self._add_message("error", f"错误：{exc}")
        finally:
            self.busy = False
            self._run_started_at = None
            input_box = self.query_one("#input", Input)
            input_box.disabled = False
            input_box.focus()
            self._update_chrome("ready")

    async def _handle_slash_command(self, prompt: str) -> bool:
        if self.session is None:
            return False
        result = handle_command(self.session, prompt)
        if not result.handled:
            return False
        if result.clear_requested:
            await self._clear_messages()
            self.query_one("#tools", RichLog).clear()
            self.current_phase = "general"
            self.phase_confidence = 0.0
            self.phase_reason = ""
            self.current_task = ""
            self.input_tokens = 0
            self.output_tokens = 0
            self._update_chrome("ready")
        if result.message:
            await self._add_message("error" if result.is_error else "system", result.message)
        if result.exit_requested:
            self.exit()
        return True

    async def handle_agent_event(self, event: AgentEvent) -> None:
        tools = self.query_one("#tools", RichLog)
        if event.type in {"text_delta", "text"}:
            await self._append_assistant_text(str(event.data.get("text") or ""))
        elif event.type == "tool_start":
            name = event.data.get("name")
            short_input = self._shorten(str(event.data.get("input") or ""), 80)
            tools.write(f"[{PALETTE['muted']}]▶[/{PALETTE['muted']}] [bold {PALETTE['text']}]{escape(str(name or 'tool'))}[/bold {PALETTE['text']}] [{PALETTE['muted']}]{escape(short_input)}[/{PALETTE['muted']}]")
            self.current_task = str(name or "tool")
            self._update_chrome(f"tool: {name}")
        elif event.type == "tool_result":
            output = self._shorten(str(event.data.get("output") or ""), 600)
            name = escape(str(event.data.get("name") or "tool"))
            exit_code = escape(str(event.data.get("exit_code") or 0))
            tools.write(f"[{PALETTE['success']}]✓[/{PALETTE['success']}] [bold {PALETTE['text']}]{name}[/bold {PALETTE['text']}] [{PALETTE['muted']}]exit={exit_code}[/{PALETTE['muted']}]")
            if output:
                tools.write(f"[{PALETTE['muted']}]{escape(output)}[/{PALETTE['muted']}]")
        elif event.type == "tool_error":
            output = self._shorten(str(event.data.get("output") or ""), 600)
            name = escape(str(event.data.get("name") or "tool"))
            exit_code = escape(str(event.data.get("exit_code") or 1))
            tools.write(f"[{PALETTE['error']}]✗[/{PALETTE['error']}] [bold {PALETTE['text']}]{name}[/bold {PALETTE['text']}] [{PALETTE['muted']}]exit={exit_code}[/{PALETTE['muted']}]")
            if output:
                tools.write(f"[{PALETTE['error']}]{escape(output)}[/{PALETTE['error']}]")
        elif event.type == "phase_update":
            self.current_phase = str(event.data.get("phase") or "general")
            try:
                self.phase_confidence = float(event.data.get("confidence") or 0.0)
            except (TypeError, ValueError):
                self.phase_confidence = 0.0
            self.phase_reason = str(event.data.get("reason") or "")
            self.current_task = str(event.data.get("current_task") or "")
            await self._add_message(
                "system",
                f"当前阶段：{PHASE_LABELS.get(self.current_phase, '通用')}（置信度 {self.phase_confidence:.2f}，任务：{self.current_task}）",
            )
            self._update_chrome("running")
        elif event.type == "token_update":
            self.input_tokens = int(event.data.get("input_tokens") or self.input_tokens)
            self.output_tokens = int(event.data.get("output_tokens") or self.output_tokens)
            self._update_chrome("running")
        elif event.type == "context_warning":
            await self._add_message("system", f"上下文提醒：{event.data.get('level')}")
        elif event.type == "progress_saved":
            await self._add_message("system", f"已保存进度：{event.data.get('path')}")
        elif event.type == "done":
            self._update_chrome("ready")

    async def action_clear(self) -> None:
        await self._clear_messages()
        self.query_one("#tools", RichLog).clear()
        if self.session is not None:
            self.session.clear()
        self.current_phase = "general"
        self.phase_confidence = 0.0
        self.phase_reason = ""
        self.current_task = ""
        self.input_tokens = 0
        self.output_tokens = 0
        self._update_chrome("ready")

    async def _add_message(self, role: str, text: str) -> Static:
        messages = self.query_one("#messages", VerticalScroll)
        class_name = {
            "error": "error-message",
            "system": "system-message",
        }.get(role, "message")
        widget = Static(self._format_message(role, text), classes=f"message {class_name}")
        await messages.mount(widget)
        self._scroll_messages()
        return widget

    async def _append_assistant_text(self, text: str) -> None:
        if not text:
            return
        self._current_assistant.append(text)
        combined = "".join(self._current_assistant)
        if self._assistant_widget is None:
            self._assistant_widget = await self._add_message("assistant", combined)
        else:
            self._assistant_widget.update(self._format_message("assistant", combined))
            self._scroll_messages()

    async def _clear_messages(self) -> None:
        await self.query_one("#messages", VerticalScroll).remove_children()
        self._current_assistant = []
        self._assistant_widget = None

    def _update_command_menu(self, value: str) -> None:
        if not value.startswith("/"):
            self._hide_command_menu()
            return
        self._filtered_commands = [(command.name, command.description) for command in complete_commands(value)]
        if not self._filtered_commands:
            self._hide_command_menu()
            return
        self._menu_index = min(self._menu_index, len(self._filtered_commands) - 1)
        self._render_command_menu()

    def _render_command_menu(self) -> None:
        menu = self.query_one("#command-menu", Static)
        lines: list[str] = []
        for index, (name, description) in enumerate(self._filtered_commands):
            if index == self._menu_index:
                lines.append(f"[bold {PALETTE['accent_2']}]▸[/bold {PALETTE['accent_2']}] [bold {PALETTE['text']}]{escape(name)}[/bold {PALETTE['text']}] [{PALETTE['muted']}]— {escape(description)}[/{PALETTE['muted']}]")
            else:
                lines.append(f"[{PALETTE['muted']}]  {escape(name)} — {escape(description)}[/{PALETTE['muted']}]")
        lines.append(f"[{PALETTE['muted']}]↑↓ 选择  Tab 补全  Enter 执行  Esc 取消[/{PALETTE['muted']}]")
        menu.update("\n".join(lines))
        menu.add_class("visible")

    def _hide_command_menu(self) -> None:
        self._filtered_commands = []
        self._menu_index = 0
        menu = self.query_one("#command-menu", Static)
        menu.update("")
        menu.remove_class("visible")

    def _scroll_messages(self) -> None:
        self.query_one("#messages", VerticalScroll).scroll_end(animate=False)

    def _format_message(self, role: str, text: str) -> str:
        escaped = escape(text)
        if role == "user":
            return f"[bold {PALETTE['accent_2']}]>[/bold {PALETTE['accent_2']}] [{PALETTE['text']}]{escaped}[/{PALETTE['text']}]"
        if role == "assistant":
            return f"[{PALETTE['text']}]{escaped}[/{PALETTE['text']}]"
        if role == "error":
            return f"[bold {PALETTE['error']}]error[/bold {PALETTE['error']}] {escaped}"
        return f"[{PALETTE['muted']}]{escaped}[/{PALETTE['muted']}]"

    def _update_chrome(self, status: str) -> None:
        self.query_one("#status", Static).update(self._status_panel_markup())
        self.query_one("#statusbar", Static).update(self._status_bar_markup(status))
        self._apply_phase_class()

    def _status_panel_markup(self) -> str:
        model = self.config.model if self.config else "unknown"
        backend = self.config.backend.type if self.config else "unknown"
        total_tokens = self.input_tokens + self.output_tokens
        pct = round((total_tokens / CONTEXT_MAX_TOKENS) * 100)
        token_color = token_style(total_tokens)
        phase_color = PHASE_STYLES.get(self.current_phase, PHASE_STYLES["general"])
        phase_label = PHASE_LABELS.get(self.current_phase, PHASE_LABELS["general"])
        return (
            f"[{PALETTE['muted']}]后端:[/{PALETTE['muted']}] [{PALETTE['text']}]{escape(backend)}[/{PALETTE['text']}] [{PALETTE['muted']}]│[/{PALETTE['muted']}] "
            f"[{PALETTE['muted']}]阶段:[/{PALETTE['muted']}] [{phase_color}]{phase_label}[/{phase_color}] [{PALETTE['muted']}]│[/{PALETTE['muted']}] "
            f"[{PALETTE['muted']}]Token:[/{PALETTE['muted']}] [{token_color}]{format_tokens(total_tokens)} / {format_tokens(CONTEXT_MAX_TOKENS)} ({pct}%)[/{token_color}]\n"
            f"[{PALETTE['muted']}]模型:[/{PALETTE['muted']}] [{PALETTE['text']}]{escape(model)}[/{PALETTE['text']}] [{PALETTE['muted']}]│[/{PALETTE['muted']}] "
            f"[{PALETTE['muted']}]工具:[/{PALETTE['muted']}] [{PALETTE['text']}]7[/{PALETTE['text']}] [{PALETTE['muted']}]│[/{PALETTE['muted']}] "
            f"[{PALETTE['muted']}]审计:[/{PALETTE['muted']}] [{PALETTE['success']}]on[/{PALETTE['success']}]"
        )

    def _status_bar_markup(self, status: str) -> str:
        phase_color = PHASE_STYLES.get(self.current_phase, PHASE_STYLES["general"])
        phase_label = PHASE_LABELS.get(self.current_phase, PHASE_LABELS["general"])
        total_tokens = self.input_tokens + self.output_tokens
        elapsed = self._elapsed_text()
        if self.busy:
            task = escape(self.current_task or "处理中...")
            state = f"[{PALETTE['accent_2']}]▶[/{PALETTE['accent_2']}] [{PALETTE['text']}]{task}[/{PALETTE['text']}]"
        else:
            state = f"[{PALETTE['muted']}]idle[/{PALETTE['muted']}]"
        return f"[{phase_color}][{phase_label}][/{phase_color}] {state} [{PALETTE['muted']}]│[/{PALETTE['muted']}] [{PALETTE['muted']}]{format_tokens(total_tokens)} tokens[/{PALETTE['muted']}] [{PALETTE['muted']}]│[/{PALETTE['muted']}] [{PALETTE['muted']}]{elapsed}[/{PALETTE['muted']}]"

    def _status_plain(self, phase: str) -> str:
        if self.session is None:
            return f"status={phase} session=uninitialized"
        return self.session.status_plain()

    def _apply_phase_class(self) -> None:
        input_box = self.query_one("#input", Input)
        for phase in PHASE_CLASS_NAMES:
            input_box.remove_class(f"phase-{phase}")
        input_box.add_class(f"phase-{self.current_phase if self.current_phase in PHASE_STYLES else 'general'}")

    def _elapsed_text(self) -> str:
        if self._run_started_at is None:
            return "00:00"
        elapsed = round(time.monotonic() - self._run_started_at)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _shorten(self, text: str, limit: int) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit] + "…"


def run_tui(root: Path) -> None:
    WeaverTuiApp(root).run()
