from __future__ import annotations

from pathlib import Path
from typing import Any

from .types import LoadedSkill, SkillSource

_ALLOWED_TOOL_KEYS = ("allowed_tools", "allowed-tools", "tools")


def parse_skill_file(path: Path, source: SkillSource, fallback_name: str | None = None) -> LoadedSkill:
    text = path.read_text(encoding="utf-8")
    frontmatter: dict[str, Any] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            frontmatter = _normalize_frontmatter(_parse_frontmatter(text[4:end]))
            body = text[end + 4 :].lstrip("\r\n")
    name = str(frontmatter.get("name") or fallback_name or path.parent.name).strip()
    description = str(frontmatter.get("description") or "").strip()
    allowed_tools = _as_tuple(frontmatter.get("allowed_tools"))
    if not name:
        raise ValueError(f"Skill {path} is missing a name")
    if not description:
        description = body.strip().splitlines()[0][:120] if body.strip() else "No description"
    return LoadedSkill(
        name=name,
        description=description,
        body=body,
        source=source,
        source_path=path,
        allowed_tools=allowed_tools,
        frontmatter=frontmatter,
    )


def _normalize_frontmatter(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    for key in _ALLOWED_TOOL_KEYS:
        if key in normalized:
            normalized["allowed_tools"] = _as_tuple(normalized[key])
            break
    return normalized


def _parse_frontmatter(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_items: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if current_key and stripped.startswith("-"):
            current_items.append(_unquote(stripped[1:].strip()))
            continue
        if current_key:
            data[current_key] = current_items
            current_key = None
            current_items = []
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        clean_key = key.strip()
        clean_value = value.strip()
        if clean_value == "":
            current_key = clean_key
            current_items = []
        else:
            data[clean_key] = _parse_value(clean_value)
    if current_key:
        data[current_key] = current_items
    return data


def _parse_value(value: str) -> Any:
    if value == "":
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_unquote(item.strip()) for item in inner.split(",") if item.strip()]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return _unquote(value)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _as_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()
