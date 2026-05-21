from __future__ import annotations

from pathlib import Path

from .parser import parse_skill_file
from .types import LoadedSkill, SkillSource


class SkillLoader:
    def __init__(self, root: Path):
        self.root = root
        self.warnings: list[str] = []

    def load_all(self) -> list[LoadedSkill]:
        self.warnings.clear()
        skills: dict[str, LoadedSkill] = {}
        for source, directory in self._skill_dirs():
            for path in sorted(directory.glob("*/SKILL.md")) if directory.exists() else []:
                try:
                    skill = parse_skill_file(path, source, fallback_name=path.parent.name)
                except (OSError, ValueError) as exc:
                    self.warnings.append(f"{path}: {exc}")
                    continue
                skills[skill.name] = skill
        return [skills[name] for name in sorted(skills)]

    def _skill_dirs(self) -> list[tuple[SkillSource, Path]]:
        return [("project", self.root / ".weaver" / "skills")]
