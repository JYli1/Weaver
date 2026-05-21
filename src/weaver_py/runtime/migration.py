from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MigrationResult:
    copied_skills: list[str] = field(default_factory=list)
    skipped_skills: list[str] = field(default_factory=list)
    imported_mcp_servers: list[str] = field(default_factory=list)
    skipped_mcp_servers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def message(self) -> str:
        lines = ["Claude Code project config migration:"]
        lines.append(f"  copied skills: {', '.join(self.copied_skills) if self.copied_skills else 'none'}")
        lines.append(f"  skipped skills: {', '.join(self.skipped_skills) if self.skipped_skills else 'none'}")
        lines.append(f"  imported MCP servers to .mcp.json: {', '.join(self.imported_mcp_servers) if self.imported_mcp_servers else 'none'}")
        lines.append(f"  skipped MCP servers: {', '.join(self.skipped_mcp_servers) if self.skipped_mcp_servers else 'none'}")
        if self.warnings:
            lines.append("  warnings:")
            lines.extend(f"    {warning}" for warning in self.warnings)
        lines.append("  skills runtime config: .weaver/skills/")
        lines.append("  MCP runtime config: .mcp.json")
        return "\n".join(lines)


def migrate_claude_project_config(root: Path) -> MigrationResult:
    result = MigrationResult()
    _migrate_skills(root, result)
    _migrate_mcp_servers(root, result)
    return result


def _migrate_skills(root: Path, result: MigrationResult) -> None:
    source_root = root / ".claude" / "skills"
    target_root = root / ".weaver" / "skills"
    if not source_root.exists():
        return
    for source_path in sorted(source_root.glob("*/SKILL.md")):
        name = source_path.parent.name
        target_path = target_root / name / "SKILL.md"
        if target_path.exists():
            result.skipped_skills.append(name)
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, target_path)
        except OSError as exc:
            result.warnings.append(f"failed to copy skill {name}: {exc}")
            continue
        result.copied_skills.append(name)


def _migrate_mcp_servers(root: Path, result: MigrationResult) -> None:
    imported: dict[str, Any] = {}
    for path in (root / ".claude" / "settings.json",):
        data = _load_json(path, result)
        servers = data.get("mcpServers") or data.get("mcp_servers")
        if isinstance(servers, dict):
            imported.update({str(name): cfg for name, cfg in servers.items() if isinstance(cfg, dict)})
    if not imported:
        return

    mcp_path = root / ".mcp.json"
    mcp_config = _load_json(mcp_path, result)
    existing = mcp_config.get("mcpServers") or mcp_config.get("mcp_servers") or {}
    if not isinstance(existing, dict):
        existing = {}
    merged = dict(existing)
    for name, cfg in sorted(imported.items()):
        if name in merged:
            result.skipped_mcp_servers.append(name)
            continue
        merged[name] = cfg
        result.imported_mcp_servers.append(name)
    mcp_config["mcpServers"] = merged
    if "mcp_servers" in mcp_config:
        del mcp_config["mcp_servers"]
    try:
        mcp_path.write_text(json.dumps(mcp_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        result.warnings.append(f"failed to write .mcp.json: {exc}")


def _load_json(path: Path, result: MigrationResult) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.warnings.append(f"failed to read {path}: {exc}")
        return {}
    return data if isinstance(data, dict) else {}
