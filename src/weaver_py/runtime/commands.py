from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from weaver_py.config import load_config
from weaver_py.mcp import McpManager
from weaver_py.security import build_writeup

from .migration import migrate_claude_project_config
from .report import save_session_report


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str
    aliases: tuple[str, ...] = ()


@dataclass
class CommandResult:
    handled: bool
    message: str = ""
    exit_requested: bool = False
    clear_requested: bool = False
    report_path: Path | None = None
    is_error: bool = False


COMMANDS = [
    SlashCommand("/status", "显示当前会话状态"),
    SlashCommand("/clear", "清空界面和当前会话"),
    SlashCommand("/report", "生成本次会话报告"),
    SlashCommand("/tools", "显示当前可用工具"),
    SlashCommand("/skills", "查看和重载 skills"),
    SlashCommand("/mcp", "查看和重载 MCP 服务器"),
    SlashCommand("/permissions", "显示当前权限和安全策略"),
    SlashCommand("/target", "设置当前 CTF/lab target"),
    SlashCommand("/note", "添加当前题目 note"),
    SlashCommand("/evidence", "查看当前 evidence"),
    SlashCommand("/writeup", "生成 CTF/lab writeup 草稿"),
    SlashCommand("/init", "显示 Weaver 项目初始化建议"),
    SlashCommand("/help", "显示帮助信息"),
    SlashCommand("/exit", "正常退出并保存会话报告", aliases=("/quit", "exit", "quit")),
]


def list_commands() -> list[SlashCommand]:
    return list(COMMANDS)


def complete_commands(prefix: str) -> list[SlashCommand]:
    if not prefix.startswith("/"):
        return []
    lowered = prefix.lower()
    return [command for command in COMMANDS if command.name.startswith(lowered)]


def handle_command(session: Any, prompt: str) -> CommandResult:
    command = prompt.strip()
    if not command:
        return CommandResult(handled=True)
    resolved = _resolve_command(command.split()[0])
    if resolved is None:
        if command.startswith("/"):
            suggestions = [item.name for item in COMMANDS if command[1:].lower() in item.name.lower()]
            suffix = f"\n你是不是想输入: {', '.join(suggestions)}" if suggestions else ""
            return CommandResult(handled=True, message=f"未知命令：{command}{suffix}", is_error=True)
        return CommandResult(handled=False)

    if resolved.name == "/help":
        lines = ["可用命令："]
        for item in COMMANDS:
            lines.append(f"  {item.name} — {item.description}")
        return CommandResult(handled=True, message="\n".join(lines))

    if resolved.name == "/status":
        return CommandResult(handled=True, message=session.status_plain())

    if resolved.name == "/clear":
        session.clear()
        return CommandResult(handled=True, message="已清空当前会话。", clear_requested=True)

    if resolved.name == "/report":
        path = save_session_report(session, reason="manual")
        if path is None:
            return CommandResult(handled=True, message="当前 session 无交互记录。")
        return CommandResult(handled=True, message=f"报告已保存至: {path}", report_path=path)

    if resolved.name == "/tools":
        tools = ", ".join(schema["name"] for schema in session.registry.schemas())
        return CommandResult(handled=True, message=f"可用工具：{tools}")

    if resolved.name == "/skills":
        return CommandResult(handled=True, message=_skills_message(session, command))

    if resolved.name == "/mcp":
        return CommandResult(handled=True, message=_mcp_message(session, command))

    if resolved.name == "/permissions":
        return CommandResult(handled=True, message=_permissions_message(session))

    if resolved.name == "/target":
        parts = command.split(maxsplit=1)
        value = parts[1].strip() if len(parts) > 1 else ""
        if not value:
            return CommandResult(handled=True, message="用法：/target <URL、host、文件或题目目标>", is_error=True)
        session.security.set_target(value)
        return CommandResult(handled=True, message=f"Target 已设置：{session.security.target}")

    if resolved.name == "/note":
        parts = command.split(maxsplit=1)
        value = parts[1].strip() if len(parts) > 1 else ""
        if not value:
            return CommandResult(handled=True, message="用法：/note <当前题目笔记>", is_error=True)
        item = session.evidence.add_note(value, phase=session.current_phase)
        return CommandResult(handled=True, message=f"已添加 note：{item.title}")

    if resolved.name == "/evidence":
        return CommandResult(handled=True, message="\n".join(session.evidence.render_lines()))

    if resolved.name == "/writeup":
        return CommandResult(handled=True, message=build_writeup(session.security, session.evidence))

    if resolved.name == "/init":
        if command.split()[1:] == ["migrate-claude"]:
            result = migrate_claude_project_config(session.root)
            session.config = load_config(session.root)
            session.engine.config = session.config
            session.mcp = McpManager(session.config.mcp_servers)
            session._runtime_ready = False
            session.reload_skills()
            return CommandResult(handled=True, message=result.message())
        return CommandResult(handled=True, message=_init_message(session))

    if resolved.name == "/exit":
        path = save_session_report(session, reason="normal_exit")
        if path is None:
            return CommandResult(handled=True, message="当前 session 无交互记录，未生成报告。", exit_requested=True)
        return CommandResult(handled=True, message=f"报告已保存至: {path}", report_path=path, exit_requested=True)

    return CommandResult(handled=False)


def _skills_message(session: Any, command: str) -> str:
    parts = command.split()
    if len(parts) >= 2 and parts[1] == "reload":
        session.reload_skills()
        return f"已重新加载项目 skills：{len(session.skills)} 个。"
    if len(parts) >= 2:
        name = parts[1]
        skill = next((item for item in session.skills if item.name == name), None)
        if skill is None:
            return f"未知 skill：{name}"
        preview = "\n".join(skill.body.strip().splitlines()[:8]) or "(empty)"
        keys = ", ".join(sorted(skill.frontmatter)) or "none"
        allowed = ", ".join(skill.allowed_tools) or "none"
        return (
            f"Skill: {skill.name}\n"
            f"description={skill.description}\n"
            f"source={skill.source}\n"
            f"path={skill.source_path}\n"
            f"base={skill.base_dir}\n"
            f"allowed_tools={allowed}\n"
            f"frontmatter_keys={keys}\n"
            f"enabled={skill.enabled}\n\n"
            f"{preview}"
        )
    lines = ["Skills:", "  Project skills (.weaver/skills):"]
    if not session.skills:
        lines.append("    none — create .weaver/skills/<name>/SKILL.md or run /init migrate-claude")
    for skill in session.skills:
        lines.append(f"    {skill.name} — {skill.description}")
    for warning in getattr(session, "skill_warnings", []):
        lines.append(f"  warning: {warning}")
    return "\n".join(lines)


def _mcp_message(session: Any, command: str) -> str:
    parts = command.split()
    if len(parts) >= 2 and parts[1] != "reload":
        return session.mcp.server_detail(parts[1])
    return "\n".join(session.mcp.state_lines())


def _permissions_message(session: Any) -> str:
    return (
        "权限：\n"
        "  Shell 工具安全策略已启用，破坏性或高风险命令会被拒绝或要求确认。\n"
        "  工具调用会写入审计日志，敏感字段会先做脱敏。\n"
        "  审计日志：.weaver/audit/tools.jsonl\n"
        "  当前版本暂不保存按工具划分的 allowlist。"
    )


def _init_message(session: Any) -> str:
    return (
        "Weaver 项目结构：\n"
        "  .weaver/settings.json                 Weaver 本地模型、密钥和报告设置\n"
        "  .weaver/skills/<name>/SKILL.md       项目 skills\n"
        "  .mcp.json                            项目或第三方 MCP 服务器\n"
        "  CLAUDE.md                            加载到 Weaver 的项目上下文\n\n"
        "迁移：\n"
        "  /init migrate-claude                 导入项目 .claude/skills，并把 .claude MCP 配置合并到 .mcp.json\n\n"
        "Skill frontmatter 示例：\n"
        "  ---\n"
        "  name: web-recon\n"
        "  description: Web reconnaissance workflow guidance\n"
        "  allowed-tools: [Read, Grep, Bash, PowerShell]\n"
        "  ---"
    )


def _resolve_command(prompt: str) -> SlashCommand | None:
    lowered = prompt.lower()
    for command in COMMANDS:
        if lowered == command.name or lowered in command.aliases:
            return command
    return None
