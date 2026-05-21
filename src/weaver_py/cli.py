from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any

from weaver_py.tui.theme import PALETTE

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.markup import escape
    from rich.panel import Panel
    from rich.theme import Theme
except ModuleNotFoundError:
    Console = None
    Markdown = None
    Panel = None
    Theme = None
    escape = None

RICH_THEME = (
    Theme(
        {
            "markdown.paragraph": PALETTE["text"],
            "markdown.text": PALETTE["text"],
            "markdown.strong": f"bold {PALETTE['text']}",
            "markdown.em": f"italic {PALETTE['accent_soft']}",
            "markdown.h1": f"bold {PALETTE['accent_soft']}",
            "markdown.h2": f"bold {PALETTE['accent_2']}",
            "markdown.h3": f"bold {PALETTE['cyan']}",
            "markdown.code": f"{PALETTE['accent_2']} on {PALETTE['surface_alt']}",
            "markdown.code_block": PALETTE["text"],
            "markdown.block_quote": PALETTE["muted"],
            "markdown.item.bullet": PALETTE["accent"],
            "markdown.link": f"underline {PALETTE['accent_2']}",
        }
    )
    if Theme
    else None
)
console = Console(theme=RICH_THEME) if Console else None


def require_runtime_dependencies() -> None:
    if console is None:
        raise RuntimeError("Missing dependency: rich. Run `python -m pip install -e .` in the Weaver project.")


def build_registry(root: Path | None = None) -> Any:
    from weaver_py.runtime import build_default_registry

    return build_default_registry(root)


def _configure_output_encoding() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _supports_unicode() -> bool:
    encoding = sys.stdout.encoding or ""
    try:
        "●⎿╭─╮╰╯│".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _print_system(message: str, prefix: str, error: bool = False, title: str = "System") -> None:
    style = "red" if error else "dim"
    if "\n" in message and Panel is not None:
        console.print(Panel(message, title=title, border_style=style, padding=(0, 1)))
        return
    for line in message.splitlines() or [""]:
        console.print(f"[{style}]{prefix}{line}[/{style}]")


def _elapsed_text(started_at: float | None) -> str:
    if started_at is None:
        return "00:00"
    elapsed = max(0, int(time.monotonic() - started_at))
    return f"{elapsed // 60:02d}:{elapsed % 60:02d}"


def _status_markup(
    label: str,
    started_at: float | None,
    phase: str,
    task: str,
    input_tokens: int,
    output_tokens: int,
    separator: str,
) -> str:
    from weaver_py.tui.theme import CONTEXT_MAX_TOKENS, format_tokens, token_style

    used = input_tokens + output_tokens
    token_part = ""
    if used > 0:
        style = token_style(used, CONTEXT_MAX_TOKENS)
        token_part = f" {separator} ctx [{style}]{format_tokens(used)}/{format_tokens(CONTEXT_MAX_TOKENS)}[/{style}]"
    return f"[{PALETTE['muted']}]  ⎿ {label} {separator} {_elapsed_text(started_at)}{token_part}[/{PALETTE['muted']}]"


def _input_rule(use_unicode: bool) -> str:
    char = "─" if use_unicode else "-"
    width = min(getattr(console, "width", 88), 160)
    return char * width


def _print_input_box(use_unicode: bool) -> None:
    return


def _prompt_marker(use_unicode: bool) -> str:
    return "❯ " if use_unicode else "> "


def _print_shortcut_hint(use_unicode: bool) -> None:
    return


def _print_user_prompt(prompt: str) -> None:
    console.print(f"[bold {PALETTE['text']}]>[/bold {PALETTE['text']}] {escape(prompt)}")


def _print_assistant_markdown(text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    if Markdown is None:
        console.print(cleaned)
        return
    console.print(Markdown(cleaned, code_theme="ansi_dark"))


async def run_cli(root: Path) -> int:
    require_runtime_dependencies()

    from weaver_py.runtime import WeaverSession, handle_command, list_commands
    from weaver_py.ui import Choice, SimpleTerminalSelector, TranscriptRenderer, render_banner

    use_unicode = _supports_unicode()
    separator = "·" if use_unicode else "-"
    system_prefix = "  ⎿ " if use_unicode else "  | "
    renderer = TranscriptRenderer(unicode=use_unicode)
    assistant_chunks: list[str] = []
    run_started_at: float | None = None
    current_phase = "general"
    current_task = ""
    input_tokens = 0
    output_tokens = 0

    status_visible = False
    active_tool_line = False

    def clear_terminal_line() -> None:
        sys.stdout.write("\r\x1b[K")
        sys.stdout.flush()

    def print_status(label: str, end: str = "\n") -> None:
        console.print(
            _status_markup(label, run_started_at, current_phase, current_task, input_tokens, output_tokens, separator),
            highlight=False,
            end=end,
        )

    def render_status_line(label: str) -> None:
        nonlocal status_visible
        clear_terminal_line()
        print_status(label, end="")
        status_visible = True

    def print_elapsed_line(elapsed: str) -> None:
        clear_terminal_line()
        console.print(f"[{PALETTE['muted']}]  ⎿ 执行耗时 {elapsed}[/{PALETTE['muted']}]")

    def clear_status_line() -> None:
        nonlocal status_visible
        if status_visible:
            clear_terminal_line()
            status_visible = False

    async def update_running_status() -> None:
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"] if use_unicode else ["-", "\\", "|", "/"]
        index = 0
        while run_started_at is not None:
            if not active_tool_line:
                render_status_line(f"{spinner[index % len(spinner)]} 正在思考")
                index += 1
            await asyncio.sleep(0.2)

    def prepare_content_output() -> None:
        nonlocal active_tool_line
        clear_status_line()
        if active_tool_line:
            clear_terminal_line()
            active_tool_line = False

    def flush_assistant_chunks() -> None:
        if not assistant_chunks:
            return
        if sys.stdin.isatty():
            prepare_content_output()
        _print_assistant_markdown("".join(assistant_chunks))
        assistant_chunks.clear()

    async def render_event(event: Any) -> None:
        nonlocal active_tool_line, current_phase, current_task, input_tokens, output_tokens
        if event.type in {"text", "text_delta"}:
            assistant_chunks.append(str(event.data.get("text") or ""))
            return
        if event.type in {"tool_start", "tool_result", "tool_error", "done"}:
            flush_assistant_chunks()
        if event.type == "token_update":
            input_tokens = int(event.data.get("input_tokens") or input_tokens)
            output_tokens = int(event.data.get("output_tokens") or output_tokens)
            return
        if event.type == "phase_update":
            current_phase = str(event.data.get("phase") or current_phase)
            current_task = str(event.data.get("current_task") or current_task)
            return
        if event.type == "tool_start":
            current_task = f"正在执行 {event.data.get('name') or 'tool'}"
        lines = renderer.render_event(event)
        if not sys.stdin.isatty():
            for line in lines:
                console.print(line)
            return
        if event.type == "tool_start" and lines:
            clear_status_line()
            console.print(lines[0], end="")
            active_tool_line = True
            return
        if event.type in {"tool_result", "tool_error"} and lines:
            if active_tool_line:
                clear_terminal_line()
            console.print(lines[0])
            for line in lines[1:]:
                console.print(line)
            active_tool_line = False
            return
        if event.type == "done":
            clear_status_line()
            active_tool_line = False

    try:
        session = WeaverSession(root=root, event_handler=render_event)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print("Set ANTHROPIC_API_KEY or configure ~/.weaver/settings.json.")
        return 1

    console.print(render_banner(session.config, root, unicode=use_unicode, width=min(console.width, 126)), style=PALETTE["text"])
    selector = SimpleTerminalSelector()
    while True:
        try:
            _print_input_box(use_unicode)
            prompt = await asyncio.to_thread(input, _prompt_marker(use_unicode))
            if not sys.stdin.isatty():
                console.print()
            _print_shortcut_hint(use_unicode)
        except EOFError:
            result = handle_command(session, "/exit")
            if result.message:
                _print_system(result.message, system_prefix)
            await session.mcp.shutdown()
            console.print()
            return 0
        except KeyboardInterrupt:
            _print_system("已中断。输入 /exit 可正常退出并生成报告。", system_prefix)
            continue
        prompt = prompt.strip()
        if not prompt:
            continue

        if prompt == "/":
            choice = await selector.choose(
                "Commands",
                [Choice(id=command.name, label=command.name, description=command.description) for command in list_commands()],
            )
            if choice is None:
                _print_system("未选择命令。", system_prefix)
                continue
            prompt = choice.id

        if prompt == "/mcp reload":
            await session.reload_mcp()
            _print_system("已重新加载 MCP 服务器。", system_prefix)
            continue

        command_result = handle_command(session, prompt)
        if command_result.handled:
            if command_result.clear_requested:
                console.clear()
                console.print(render_banner(session.config, root, unicode=use_unicode, width=min(console.width, 126)), style=PALETTE["text"])
            if command_result.message:
                title = "Status" if prompt == "/status" else "System"
                _print_system(command_result.message, system_prefix, error=command_result.is_error, title=title)
            if command_result.exit_requested:
                _print_system("再见。", system_prefix)
                await session.mcp.shutdown()
                return 0
            continue

        run_started_at = time.monotonic()
        current_task = "正在思考"
        assistant_chunks.clear()
        timer_task: asyncio.Task[None] | None = None
        if not sys.stdin.isatty():
            _print_user_prompt(prompt)
            print_status("正在思考")
        else:
            timer_task = asyncio.create_task(update_running_status())
        try:
            await session.ask(prompt)
        finally:
            elapsed = _elapsed_text(run_started_at)
            run_started_at = None
            if timer_task is not None:
                await timer_task
            clear_status_line()
            if active_tool_line:
                clear_terminal_line()
            print_elapsed_line(elapsed)


classic = run_cli


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weaver Python runtime")
    parser.add_argument("--classic", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--tui", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cwd", default=".", help="Project root directory")
    return parser.parse_args()


def main() -> int:
    _configure_output_encoding()
    args = parse_args()
    root = Path(args.cwd).expanduser().resolve()
    if args.tui:
        from weaver_py.tui import WeaverTuiApp

        WeaverTuiApp(root).run()
        return 0
    return asyncio.run(run_cli(root))


if __name__ == "__main__":
    raise SystemExit(main())
