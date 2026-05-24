from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import time
from pathlib import Path
from typing import Any

from weaver_py.tui.theme import PALETTE

try:
    from rich.cells import cell_len, set_cell_size
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
    cell_len = None
    escape = None
    set_cell_size = None

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
        "●▍┃━✓✗❯⎿╭─╮╰╯│".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _escape_markup(value: object) -> str:
    text = str(value)
    return escape(text) if escape is not None else text.replace("[", "\\[")


def _print_system(message: str, prefix: str, error: bool = False, title: str = "System") -> None:
    border_color = PALETTE["error"] if error else PALETTE["accent_dim"]
    border = "┃" if "┃" in prefix else "|"
    if "\n" in message and Panel is not None:
        console.print(Panel(message, title=title, border_style=border_color, padding=(0, 1)))
        return
    for line in message.splitlines() or [""]:
        console.print(f"[{border_color}]  {border}[/{border_color}] [{PALETTE['text']}]{_escape_markup(line)}[/{PALETTE['text']}]")


def _elapsed_text(started_at: float | None) -> str:
    if started_at is None:
        return "00:00"
    elapsed = max(0, int(time.monotonic() - started_at))
    return f"{elapsed // 60:02d}:{elapsed % 60:02d}"


def _compact_status_value(value: str, limit: int = 28) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _lab_context_markup(phase: str, task: str, target: str, evidence_count: int, separator: str) -> str:
    from weaver_py.tui.theme import PHASE_STYLES

    phase_color = PHASE_STYLES.get(phase, PALETTE["text"])
    parts = [f"[{phase_color}]{_escape_markup(phase or 'general')}[/{phase_color}]", f"ev:{evidence_count}"]
    if target:
        parts.append(f"target {_escape_markup(_compact_status_value(target))}")
    elif task:
        parts.append(_escape_markup(_compact_status_value(task)))
    return f" {separator} " + f" {separator} ".join(parts)


def _status_markup(
    label: str,
    started_at: float | None,
    phase: str,
    task: str,
    input_tokens: int,
    output_tokens: int,
    separator: str,
    target: str = "",
    evidence_count: int = 0,
) -> str:
    from weaver_py.tui.theme import CONTEXT_MAX_TOKENS, PHASE_STYLES, format_tokens, token_style

    phase_color = PHASE_STYLES.get(phase, PALETTE["text"])
    used = input_tokens + output_tokens
    token_part = ""
    if used > 0:
        style = token_style(used, CONTEXT_MAX_TOKENS)
        token_part = f" {separator} ctx [{style}]{format_tokens(used)}/{format_tokens(CONTEXT_MAX_TOKENS)}[/{style}]"
    lab_part = _lab_context_markup(phase, task, target, evidence_count, separator)
    return (
        f"[{phase_color}]  ▍[/{phase_color}]"
        f"[{PALETTE['muted']}]{_escape_markup(label)} {separator} {_elapsed_text(started_at)}{lab_part}{token_part}[/{PALETTE['muted']}]"
    )


def _failure_markup(elapsed: str) -> str:
    return f"[{PALETTE['error']}]  ▍[/{PALETTE['error']}][{PALETTE['muted']}]失败 · {elapsed}[/{PALETTE['muted']}]"


def _input_rule(use_unicode: bool, width: int | None = None) -> str:
    char = "─" if use_unicode else "-"
    line_width = width or min(getattr(console, "width", 88), 160)
    line = char * line_width
    if cell_len is not None and cell_len(line) != line_width and set_cell_size is not None:
        return set_cell_size(line, line_width)
    return line


def _fit_cell_width(text: str, width: int, use_unicode: bool) -> str:
    if width <= 0:
        return ""
    if set_cell_size is None or cell_len is None:
        if len(text) <= width:
            return text.ljust(width)
        suffix = "…" if use_unicode else "~"
        return (text[: max(0, width - len(suffix))] + suffix)[:width]
    if cell_len(text) <= width:
        return set_cell_size(text, width)
    suffix = "…" if use_unicode else "~"
    suffix_width = cell_len(suffix)
    if width <= suffix_width:
        return set_cell_size(suffix, width)
    return set_cell_size(set_cell_size(text, width - suffix_width).rstrip() + suffix, width)


def _short_target(value: str | None, limit: int = 42) -> str:
    if not value:
        return "none"
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _bottom_status_markup(phase: str, target: str | None, evidence_count: int, input_tokens: int, output_tokens: int) -> str:
    from weaver_py.tui.theme import CONTEXT_MAX_TOKENS, format_tokens, token_style

    used = input_tokens + output_tokens
    style = token_style(used, CONTEXT_MAX_TOKENS)
    safe_phase = _escape_markup(str(phase))
    safe_target = _escape_markup(_short_target(target))
    return (
        f"[{PALETTE['muted']}]  ctx [/{PALETTE['muted']}][{style}]{format_tokens(used)}/{format_tokens(CONTEXT_MAX_TOKENS)}[/{style}]"
        f" [{PALETTE['muted']}]· input {format_tokens(input_tokens)} · output {format_tokens(output_tokens)}"
        f" · phase {safe_phase} · ev {evidence_count} · target {safe_target}[/{PALETTE['muted']}]"
    )


def _render_user_prompt_block(prompt: str, use_unicode: bool, width: int | None = None) -> list[str]:
    line_width = max(24, width or min(getattr(console, "width", 88), 160))
    inner_width = line_width - 4
    top_left, top_right, bottom_left, bottom_right = ("╭", "╮", "╰", "╯") if use_unicode else ("+", "+", "+", "+")
    horizontal = "─" if use_unicode else "-"
    vertical = "│" if use_unicode else "|"
    marker = "❯" if use_unicode else ">"
    text = _fit_cell_width(f"{marker} {prompt}", inner_width, use_unicode)
    return [
        top_left + _fit_cell_width(horizontal * (line_width - 2), line_width - 2, use_unicode) + top_right,
        vertical + " " + text + " " + vertical,
        bottom_left + _fit_cell_width(horizontal * (line_width - 2), line_width - 2, use_unicode) + bottom_right,
    ]


def _print_input_box(use_unicode: bool) -> None:
    console.print(f"[{PALETTE['line_dim']}]{_input_rule(use_unicode)}[/{PALETTE['line_dim']}]")


def _prompt_marker(use_unicode: bool) -> str:
    return "❯ " if use_unicode else "> "


def _print_shortcut_hint(
    use_unicode: bool,
    phase: str = "general",
    target: str | None = None,
    evidence_count: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    console.print(f"[{PALETTE['line_dim']}]{_input_rule(use_unicode)}[/{PALETTE['line_dim']}]")
    console.print(_bottom_status_markup(phase, target, evidence_count, input_tokens, output_tokens), highlight=False)


def _clear_interactive_lines(count: int) -> None:
    sys.stdout.write("\x1b[1A\r\x1b[K" * count)
    sys.stdout.flush()


def _print_user_prompt(prompt: str, use_unicode: bool = True) -> None:
    for index, line in enumerate(_render_user_prompt_block(prompt, use_unicode)):
        if index == 1:
            escaped = escape(line) if escape is not None else line
            escaped = escaped.replace("❯", f"[{PALETTE['amber']}]❯[/{PALETTE['amber']}]")
            console.print(f"[{PALETTE['user_border']} on {PALETTE['user_bg']}]{escaped}[/{PALETTE['user_border']} on {PALETTE['user_bg']}]")
        else:
            console.print(f"[{PALETTE['user_border']}]{escape(line) if escape is not None else line}[/{PALETTE['user_border']}]")


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
    from weaver_py.ui import BannerContext, Choice, SimpleTerminalSelector, TranscriptRenderer, render_banner

    use_unicode = _supports_unicode()
    separator = "·" if use_unicode else "-"
    system_prefix = "  ┃ " if use_unicode else "  | "
    renderer = TranscriptRenderer(unicode=use_unicode)
    assistant_chunks: list[str] = []
    run_started_at: float | None = None
    current_phase = "general"
    current_task = ""
    input_tokens = 0
    output_tokens = 0

    status_visible = False
    active_tool_line = False
    active_tool_markup = ""
    last_dynamic_line = ""

    def clear_terminal_line() -> None:
        sys.stdout.write("\r\x1b[K")
        sys.stdout.flush()

    def render_dynamic_line(markup: str) -> None:
        nonlocal last_dynamic_line
        if markup == last_dynamic_line:
            return
        clear_terminal_line()
        console.print(markup, highlight=False, end="")
        last_dynamic_line = markup

    def print_status(label: str, end: str = "\n") -> None:
        console.print(
            _status_markup(
                label,
                run_started_at,
                current_phase,
                current_task,
                input_tokens,
                output_tokens,
                separator,
                session.security.target,
                session.evidence.count,
            ),
            highlight=False,
            end=end,
        )

    def render_status_line(label: str) -> None:
        nonlocal status_visible
        render_dynamic_line(
            _status_markup(
                label,
                run_started_at,
                current_phase,
                current_task,
                input_tokens,
                output_tokens,
                separator,
                session.security.target,
                session.evidence.count,
            )
        )
        status_visible = True

    def print_elapsed_line(elapsed: str, failed: bool = False) -> None:
        nonlocal last_dynamic_line
        clear_terminal_line()
        last_dynamic_line = ""
        if failed:
            console.print(_failure_markup(elapsed))
            return
        console.print(f"[{PALETTE['success']}]  ▍[/{PALETTE['success']}][{PALETTE['muted']}]完成 · {elapsed}[/{PALETTE['muted']}]")

    def clear_status_line() -> None:
        nonlocal last_dynamic_line, status_visible
        if status_visible:
            clear_terminal_line()
            last_dynamic_line = ""
            status_visible = False

    async def update_running_status() -> None:
        while run_started_at is not None:
            if active_tool_line and active_tool_markup:
                render_dynamic_line(f"{active_tool_markup} [{PALETTE['muted']}]· {_elapsed_text(run_started_at)}[/{PALETTE['muted']}]")
            elif not active_tool_line:
                render_status_line("正在思考")
            await asyncio.sleep(1.0)

    def prepare_content_output() -> None:
        nonlocal active_tool_line, active_tool_markup, last_dynamic_line
        clear_status_line()
        if active_tool_line:
            clear_terminal_line()
            active_tool_line = False
            active_tool_markup = ""
            last_dynamic_line = ""

    def flush_assistant_chunks() -> None:
        if not assistant_chunks:
            return
        if sys.stdin.isatty():
            prepare_content_output()
        _print_assistant_markdown("".join(assistant_chunks))
        assistant_chunks.clear()

    async def render_event(event: Any) -> None:
        nonlocal active_tool_line, active_tool_markup, last_dynamic_line, current_phase, current_task, input_tokens, output_tokens
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
            active_tool_markup = lines[0]
            render_dynamic_line(f"{active_tool_markup} [{PALETTE['muted']}]· {_elapsed_text(run_started_at)}[/{PALETTE['muted']}]")
            active_tool_line = True
            return
        if event.type in {"tool_result", "tool_error"} and lines:
            if active_tool_line:
                clear_terminal_line()
                last_dynamic_line = ""
            console.print(lines[0])
            for line in lines[1:]:
                console.print(line)
            active_tool_line = False
            active_tool_markup = ""
            return
        if event.type == "done":
            flush_assistant_chunks()
            clear_status_line()
            active_tool_line = False

    try:
        session = WeaverSession(root=root, event_handler=render_event)
    except ValueError as exc:
        console.print(f"[red]{_escape_markup(exc)}[/red]")
        console.print("Set ANTHROPIC_API_KEY or configure ~/.weaver/settings.json.")
        return 1

    def banner_context() -> BannerContext:
        return BannerContext(
            target=session.security.target,
            phase=session.current_phase,
            evidence_count=session.evidence.count,
        )

    console.print(render_banner(session.config, root, unicode=use_unicode, width=min(console.width, 126), context=banner_context()), style=PALETTE["text"])
    selector = SimpleTerminalSelector()
    bottom_status_visible = False

    def print_bottom_status() -> None:
        nonlocal bottom_status_visible
        _print_shortcut_hint(
            use_unicode,
            current_phase,
            session.security.target,
            session.evidence.count,
            input_tokens,
            output_tokens,
        )
        bottom_status_visible = True

    while True:
        try:
            if sys.stdin.isatty():
                prompt = await asyncio.to_thread(input, _prompt_marker(use_unicode))
                _clear_interactive_lines(3 if bottom_status_visible else 1)
                bottom_status_visible = False
            else:
                prompt = await asyncio.to_thread(input, "")
                console.print()
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

        prompt = prompt.strip().lstrip("﻿").strip()
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

        _print_user_prompt(prompt, use_unicode)

        if prompt == "/mcp reload":
            await session.reload_mcp()
            _print_system("已重新加载 MCP 服务器。", system_prefix)
            print_bottom_status()
            continue

        command_result = handle_command(session, prompt)
        if command_result.handled:
            if command_result.clear_requested:
                console.clear()
                console.print(render_banner(session.config, root, unicode=use_unicode, width=min(console.width, 126), context=banner_context()), style=PALETTE["text"])
            if command_result.message:
                title = "Status" if prompt == "/status" else "System"
                _print_system(command_result.message, system_prefix, error=command_result.is_error, title=title)
            if command_result.exit_requested:
                _print_system("再见。", system_prefix)
                await session.mcp.shutdown()
                print_bottom_status()
                return 0
            print_bottom_status()
            continue

        run_started_at = time.monotonic()
        current_task = "正在思考"
        assistant_chunks.clear()
        timer_task: asyncio.Task[None] | None = None
        if not sys.stdin.isatty():
            print_status("正在思考")
        else:
            timer_task = asyncio.create_task(update_running_status())
        request_failed = False
        try:
            await session.ask(prompt)
        except Exception as exc:
            request_failed = True
            clear_status_line()
            if active_tool_line:
                clear_terminal_line()
                active_tool_line = False
            error_type = type(exc).__name__
            error_msg = str(exc) or error_type
            _print_system(f"请求失败 ({error_type}): {error_msg}", system_prefix, error=True)
        finally:
            elapsed = _elapsed_text(run_started_at)
            run_started_at = None
            if timer_task is not None:
                timer_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await timer_task
            clear_status_line()
            if active_tool_line:
                clear_terminal_line()
            print_elapsed_line(elapsed, failed=request_failed)
            print_bottom_status()


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
