from __future__ import annotations

from typing import Any

from weaver_py.skills import LoadedSkill

from .base import BaseTool, ToolResult


class SkillTool(BaseTool):
    name = "Skill"
    description = "Load the full instructions for an enabled Weaver skill by name."
    input_schema = {
        "type": "object",
        "properties": {
            "skill": {"type": "string", "description": "Skill name to load."},
            "arguments": {"type": "string", "description": "Optional arguments to substitute for $ARGUMENTS."},
            "args": {"type": "string", "description": "Alias for arguments."},
            "input": {"type": "string", "description": "Alias for arguments."},
        },
        "required": ["skill"],
    }

    def __init__(self, skills: list[LoadedSkill], session_id: str = ""):
        self._skills = {skill.name: skill for skill in skills if skill.enabled}
        self._session_id = session_id

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        name = str(input.get("skill") or "").strip()
        arguments = _argument_text(input)
        skill = self._skills.get(name)
        if skill is None:
            available = ", ".join(sorted(self._skills)) or "none"
            return ToolResult(f"Unknown skill: {name}. Available skills: {available}", 1, is_error=True)
        body = _render_body(skill, arguments, self._session_id)
        output = (
            f"Skill: {skill.name}\n"
            f"Description: {skill.description}\n"
            f"Source: {skill.source}\n"
            f"Base directory for this skill: {skill.base_dir}\n\n"
            f"{body}"
        )
        return ToolResult(output, 0)


def _argument_text(input: dict[str, Any]) -> str:
    for key in ("arguments", "args", "input"):
        value = input.get(key)
        if value is not None:
            return str(value)
    return ""


def _render_body(skill: LoadedSkill, arguments: str, session_id: str) -> str:
    return (
        skill.body.replace("$ARGUMENTS", arguments)
        .replace("${ARGUMENTS}", arguments)
        .replace("${CLAUDE_SKILL_DIR}", str(skill.base_dir))
        .replace("${CLAUDE_SESSION_ID}", session_id)
    )
