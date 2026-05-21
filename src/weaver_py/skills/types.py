from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


SkillSource = Literal["project"]


@dataclass(frozen=True)
class LoadedSkill:
    name: str
    description: str
    body: str
    source: SkillSource
    source_path: Path
    allowed_tools: tuple[str, ...] = ()
    enabled: bool = True
    frontmatter: dict[str, Any] = field(default_factory=dict)

    @property
    def base_dir(self) -> Path:
        return self.source_path.parent
