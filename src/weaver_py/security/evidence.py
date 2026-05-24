from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EvidenceItem:
    kind: str
    title: str
    source: str = ""
    summary: str = ""
    phase: str = "general"
    created_at: datetime = field(default_factory=datetime.now)

    def one_line(self) -> str:
        source = f" 来源：{self.source}" if self.source else ""
        summary = f" — {self.summary}" if self.summary else ""
        return f"{self.title} [{self.kind}/{self.phase}]{source}{summary}"


class EvidenceStore:
    def __init__(self) -> None:
        self.items: list[EvidenceItem] = []

    @property
    def count(self) -> int:
        return len(self.items)

    def add(self, kind: str, title: str, source: str = "", summary: str = "", phase: str = "general") -> EvidenceItem:
        item = EvidenceItem(
            kind=kind.strip() or "finding",
            title=title.strip() or "未命名证据",
            source=source.strip(),
            summary=summary.strip(),
            phase=phase.strip() or "general",
        )
        self.items.append(item)
        return item

    def add_note(self, text: str, phase: str = "general") -> EvidenceItem:
        # note 也作为 evidence 保存，P0 阶段减少概念数量，/writeup 可以统一渲染。
        cleaned = text.strip()
        return self.add(kind="note", title=cleaned or "空 note", summary=cleaned, phase=phase)

    def clear(self) -> None:
        self.items.clear()

    def render_lines(self) -> list[str]:
        if not self.items:
            return ["Evidence: 暂无记录。"]
        lines = ["Evidence:"]
        for index, item in enumerate(self.items, start=1):
            lines.append(f"  {index}. {item.title} — {item.phase}")
            if item.source:
                lines.append(f"     来源：{item.source}")
            if item.summary:
                lines.append(f"     摘要：{item.summary}")
        return lines

    def as_markdown(self) -> str:
        if not self.items:
            return "- 暂无 evidence。"
        lines: list[str] = []
        for item in self.items:
            source = f"，来源：{item.source}" if item.source else ""
            summary = f"：{item.summary}" if item.summary else ""
            lines.append(f"- **{item.title}**（{item.kind}/{item.phase}{source}）{summary}")
        return "\n".join(lines)
