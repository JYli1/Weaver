from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from rich.cells import cell_len, set_cell_size
    from rich.markup import escape
except ModuleNotFoundError:
    cell_len = None
    set_cell_size = None

    def escape(value: str) -> str:
        return value.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;")

from weaver_py.tui.theme import PALETTE


ELLIPSIS = "…"


@dataclass(frozen=True)
class BannerContext:
    target: str = ""
    phase: str = "general"
    evidence_count: int = 0


def _cell_len(text: str) -> int:
    if cell_len is not None:
        return cell_len(text)
    return len(text)


def _set_cell_size(text: str, width: int) -> str:
    if set_cell_size is not None:
        return set_cell_size(text, width)
    if len(text) <= width:
        return text + " " * (width - len(text))
    return text[:width]


def _clean(value: Any) -> str:
    # banner 只占启动区，动态值统一压成单行，避免换行破坏 retro 框。
    return " ".join(str(value or "").split())


def _fit(text: str, width: int, unicode: bool = True) -> str:
    if width <= 0:
        return ""
    if _cell_len(text) <= width:
        return _set_cell_size(text, width)
    ellipsis = ELLIPSIS if unicode else "~"
    ellipsis_width = _cell_len(ellipsis)
    if width <= ellipsis_width:
        return _set_cell_size(ellipsis, width)
    truncated = _set_cell_size(text, width - ellipsis_width).rstrip()
    return _set_cell_size(f"{truncated}{ellipsis}", width)


def _center(text: str, width: int, unicode: bool = True) -> str:
    text_width = _cell_len(text)
    if text_width >= width:
        return _fit(text, width, unicode)
    left = (width - text_width) // 2
    right = width - text_width - left
    return " " * left + text + " " * right


def _styled(text: str, style: str) -> str:
    return f"[{style}]{escape(text)}[/{style}]"


def _command_row(side: str, inner_width: int, unicode: bool) -> str:
    commands = ["/help", "/status", "/target", "/evidence", "/exit"]
    plain = "  ".join(commands)
    fitted = _fit(plain, inner_width, unicode)
    command_styles = [PALETTE["cyan"], PALETTE["accent_soft"], PALETTE["amber"], PALETTE["success"], PALETTE["orange"]]
    colored = escape(fitted)
    for command, style in zip(commands, command_styles, strict=True):
        colored = colored.replace(escape(command), f"[{style}]{escape(command)}[/{style}]", 1)
    return f"{_styled(side, PALETTE['accent_dim'])} {colored} {_styled(side, PALETTE['accent_dim'])}"


def _plain_row(side: str, text: str, inner_width: int, unicode: bool, style: str) -> str:
    return f"{_styled(side, PALETTE['accent_dim'])} {_styled(_fit(text, inner_width, unicode), style)} {_styled(side, PALETTE['accent_dim'])}"


def render_banner(
    config: Any,
    root: Path,
    unicode: bool = True,
    width: int = 96,
    context: BannerContext | None = None,
) -> str:
    # Retro Field Ops：保留 worktree 的 WEAVER 大字 banner，同时接收主仓库 CTF/lab context。
    model = _clean(getattr(config, "model", "unknown")) or "unknown"
    backend = _clean(getattr(getattr(config, "backend", None), "type", "unknown")) or "unknown"
    context = context or BannerContext()
    separator = "·" if unicode else "-"
    total_width = max(72, min(width, 132))
    title = " WEAVER FIELD OPS "

    if unicode:
        horizontal = "─"
        top = "╭───" + title + horizontal * max(total_width - _cell_len(title) - 5, 1) + "╮"
        bottom = "╰" + horizontal * (total_width - 2) + "╯"
        side = "│"
        logo = [
            "██╗    ██╗███████╗ █████╗ ██╗   ██╗███████╗██████╗ ",
            "██║    ██║██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗",
            "██║ █╗ ██║█████╗  ███████║██║   ██║█████╗  ██████╔╝",
            "██║███╗██║██╔══╝  ██╔══██║╚██╗ ██╔╝██╔══╝  ██╔══██╗",
            "╚███╔███╔╝███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║",
            " ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝",
        ]
    else:
        horizontal = "-"
        top = "+---" + title + horizontal * max(total_width - len(title) - 5, 1) + "+"
        bottom = "+" + horizontal * (total_width - 2) + "+"
        side = "|"
        logo = [
            "W   W EEEEE  A  V   V EEEEE RRRR ",
            "W W W E     A A V   V E     R   R",
            "WW WW EEEE AAAAA V V  EEEE  RRRR ",
            "W   W E    A   A V V  E     R  R ",
            "W   W EEEEEA   A  V   EEEEE R   R",
        ]

    meta_parts = ["v0.1.0", "FIELD OPS", f"model {model}", f"backend {backend}"]
    meta = f" {separator} ".join(meta_parts)
    lab_parts = [f"phase {context.phase or 'general'}", f"evidence {max(0, int(context.evidence_count or 0))}"]
    if context.target:
        lab_parts.insert(0, f"target {_clean(context.target)}")
    path = _clean(root)

    rows = [_styled(top, PALETTE["accent_dim"])]
    inner_width = total_width - 4
    logo_styles = [PALETTE["amber"], PALETTE["orange"], PALETTE["warning"], PALETTE["accent_soft"], PALETTE["cyan"], PALETTE["accent_2"]]
    for index, line in enumerate(logo):
        style = logo_styles[min(index, len(logo_styles) - 1)]
        rows.append(f"{_styled(side, PALETTE['accent_dim'])} {_styled(_center(line, inner_width, unicode), style)} {_styled(side, PALETTE['accent_dim'])}")
    rows.append(_plain_row(side, _center(meta, inner_width, unicode), inner_width, unicode, PALETTE["muted"]))
    if context.target or context.phase != "general" or context.evidence_count:
        lab_text = " · ".join(lab_parts) if unicode else " - ".join(lab_parts)
        rows.append(_plain_row(side, lab_text, inner_width, unicode, PALETTE["accent_soft"]))
    rows.append(_command_row(side, inner_width, unicode))
    rows.append(_plain_row(side, path, inner_width, unicode, PALETTE["line_dim"]))
    rows.append(_styled(bottom, PALETTE["accent_dim"]))
    return "\n".join(rows)
