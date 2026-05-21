from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

WarningLevel = Literal["ok", "warning", "save_recommended", "save_required"]


@dataclass
class ProgressTracker:
    warn_tokens: int = 160_000
    recommend_save_tokens: int = 180_000
    auto_save_tokens: int = 195_000
    note_dir: Path = field(default_factory=lambda: Path("docs/progress"))

    def level(self, input_tokens: int, output_tokens: int = 0) -> WarningLevel:
        total = input_tokens + output_tokens
        if total >= self.auto_save_tokens:
            return "save_required"
        if total >= self.recommend_save_tokens:
            return "save_recommended"
        if total >= self.warn_tokens:
            return "warning"
        return "ok"

    def maybe_write_note(self, root: Path, input_tokens: int, output_tokens: int = 0) -> Path | None:
        if self.level(input_tokens, output_tokens) != "save_required":
            return None
        target_dir = root / self.note_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        path = target_dir / f"{now}-context-warning.md"
        total = input_tokens + output_tokens
        path.write_text(
            "# Weaver context warning\n\n"
            f"- time: {now}\n"
            f"- estimated input tokens: {input_tokens}\n"
            f"- estimated output tokens: {output_tokens}\n"
            f"- estimated total tokens: {total}\n\n"
            "Continue by reading `CLAUDE.md` and the latest project state.\n",
            encoding="utf-8",
        )
        return path
