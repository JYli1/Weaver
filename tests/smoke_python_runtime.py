from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) if not current else str(SRC) + os.pathsep + current
    return env


from weaver_py.agent import AgentEngine
from weaver_py.agent.events import AgentEvent
from weaver_py.config import McpServerConfig, WeaverConfig, load_config
from weaver_py.runtime import WeaverSession, build_default_registry, handle_command
from weaver_py.security import EvidenceStore, SecurityContext, build_writeup
from weaver_py.ui import BannerContext, TranscriptRenderer, render_banner


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    if not ok:
        raise SystemExit(1)


def run_banner_smoke() -> None:
    config = WeaverConfig(api_key="test-key", model="banner-model")
    context = BannerContext(target="http://banner.local", phase="enum", evidence_count=2)
    unicode_banner = render_banner(config, ROOT, unicode=True, width=96, context=context)
    unicode_ok = all(
        token in unicode_banner
        for token in ("WEAVER", "FIELD OPS", "banner-model", "/target", "http://banner.local", "enum", "2")
    )
    check("unicode field ops banner", unicode_ok)

    ascii_banner = render_banner(config, ROOT, unicode=False, width=96, context=context)
    ascii_ok = all(token in ascii_banner for token in ("WEAVER", "FIELD OPS", "banner-model", "/target"))
    ascii_ok = ascii_ok and all(ch in ascii_banner for ch in ("+", "-", "|"))
    ascii_ok = ascii_ok and all(ord(ch) < 128 for ch in ascii_banner)
    check("ascii field ops banner", ascii_ok)

    narrow_banner = render_banner(config, ROOT, unicode=True, width=72, context=context)
    narrow_ok = "FIELD OPS" in narrow_banner and "banner-model" in narrow_banner and len(narrow_banner.splitlines()) >= 8
    check("narrow field ops banner", narrow_ok)

    escaped_config = WeaverConfig(api_key="test-key", model="model[demo]&x")
    escaped_context = BannerContext(target="http://banner.local/[x]&y", phase="枚举", evidence_count=12)
    escaped_banner = render_banner(escaped_config, ROOT / "[demo]&root", unicode=True, width=96, context=escaped_context)
    escaped_ok = "\\[demo]" in escaped_banner and "\\[x]" in escaped_banner and "[/target" not in escaped_banner
    check("escaped field ops banner", escaped_ok)


def run_retro_cli_palette() -> None:
    import re

    from weaver_py.tui.theme import PALETTE

    required = ["amber", "orange", "line_dim", "user_bg", "user_border", "accent_dim"]
    hex_color = re.compile(r"^#[0-9A-Fa-f]{6}$")
    missing = [name for name in required if name not in PALETTE]
    invalid = [
        f"{name}={PALETTE[name]!r}"
        for name in required
        if name in PALETTE and (not isinstance(PALETTE[name], str) or not hex_color.fullmatch(PALETTE[name]))
    ]
    detail = "; ".join(
        part
        for part in (
            f"missing: {', '.join(missing)}" if missing else "",
            f"invalid: {', '.join(invalid)}" if invalid else "",
        )
        if part
    )
    check("retro cli palette", not missing and not invalid, detail)


def run_retro_banner_smoke() -> None:
    from rich.cells import cell_len
    from rich.text import Text

    from weaver_py.tui.theme import PALETTE

    config = WeaverConfig(api_key="test-key", model="retro-model")
    unicode_config = WeaverConfig(api_key="test-key", model="复古模型")
    unicode_root = Path("D:/实验/项目/Weaver安全实验室")
    banner = render_banner(config, ROOT, unicode=True, width=110)
    unicode_banner = render_banner(unicode_config, unicode_root, unicode=True, width=72)
    ascii_banner = render_banner(config, ROOT, unicode=False, width=80)

    def plain_lines(value: str) -> list[str]:
        return [Text.from_markup(line).plain for line in value.splitlines()]

    unicode_widths_ok = all(cell_len(line) == 72 for line in plain_lines(unicode_banner))
    ascii_widths_ok = all(cell_len(line) == 80 for line in plain_lines(ascii_banner))

    ok = "WEAVER" in banner
    ok = ok and "FIELD OPS" in banner
    ok = ok and "retro-model" in banner
    ok = ok and "╭" in banner and "╰" in banner
    ok = ok and "█" in banner
    ok = ok and f"[{PALETTE['amber']}]" in banner and f"[{PALETTE['cyan']}]" in banner
    ok = ok and all(command in banner for command in ("/help", "/status", "/target", "/evidence", "/exit"))
    ok = ok and "WEAVER" in ascii_banner and "+" in ascii_banner
    ok = ok and unicode_widths_ok and ascii_widths_ok
    check("retro startup banner", ok)


def run_retro_cli_render_helpers() -> None:
    from rich.cells import cell_len
    from rich.markup import escape as markup_escape

    from weaver_py.cli import _bottom_status_markup, _input_rule, _render_user_prompt_block

    prompt_lines = _render_user_prompt_block("你好", True, width=48)
    block = "\n".join(prompt_lines)
    status = _bottom_status_markup("general", "http://example.local/very/long/path", 2, 1200, 345)
    long_cjk_lines = _render_user_prompt_block("你好世界" * 12, True, width=32)
    status_markup = _bottom_status_markup("gen[red]", "http://example.local/[red]x[/red]", 1, 1, 1)

    ok = "you" not in block.lower()
    ok = ok and "❯ 你好" in block
    ok = ok and "╭" in block and "╰" in block
    ok = ok and "ctx" in status and "phase general" in status and "ev 2" in status
    ok = ok and "target http://example.local" in status
    ok = ok and len(_input_rule(True, width=20)) == 20
    ok = ok and all(cell_len(line) == 48 for line in prompt_lines)
    ok = ok and all(cell_len(line) == 32 for line in long_cjk_lines)
    ok = ok and markup_escape("gen[red]") in status_markup
    ok = ok and markup_escape("http://example.local/[red]x[/red]") in status_markup
    check("retro cli render helpers", ok)


def run_shell_registry_order() -> None:
    registry = build_default_registry(ROOT)
    names = [schema["name"] for schema in registry.schemas()]
    if sys.platform == "win32":
        ok = "PowerShell" in names and "Bash" in names and names.index("PowerShell") < names.index("Bash")
        check("shell registry order", ok)
    else:
        check("shell registry order", "Bash" in names and "PowerShell" not in names)


def run_shell_tool_descriptions() -> None:
    registry = build_default_registry(ROOT)
    descriptions = {schema["name"]: str(schema["description"]) for schema in registry.schemas()}
    if sys.platform == "win32":
        ok = "PowerShell" in descriptions and "Prefer this tool on Windows" in descriptions["PowerShell"]
        ok = ok and "Windows" in descriptions["Bash"]
        check("shell tool descriptions", ok)
    else:
        check("shell tool descriptions", "Bash" in descriptions)


def run_system_prompt_output_rules() -> None:
    from weaver_py.agent.engine import BASE_SYSTEM_PROMPT, build_system_prompt

    built = build_system_prompt(project_context="项目规则示例")
    requirements = [
        ("identity section", "## 身份与定位" in BASE_SYSTEM_PROMPT),
        ("authorization scope section", "## 授权、scope 与影响确认" in BASE_SYSTEM_PROMPT),
        ("evidence writeup section", "## Evidence 与 writeup 闭环" in BASE_SYSTEM_PROMPT),
        ("phase bookkeeping instruction", "Do not output phase bookkeeping" in BASE_SYSTEM_PROMPT),
        ("update phase tool instruction", "UpdatePhase tool only" in BASE_SYSTEM_PROMPT),
        ("evidence persistence warning", "不要承诺 runtime 会自动保存所有 evidence" in BASE_SYSTEM_PROMPT),
        ("legacy destructive action wording removed", "Do not perform destructive actions" not in BASE_SYSTEM_PROMPT),
        ("project context heading", "## 项目上下文（来自 CLAUDE.md）" in built),
        ("project context content", "项目规则示例" in built),
    ]
    failures = [name for name, passed in requirements if not passed]
    check("system prompt uses Chinese confirmation-first sections", not failures, ", ".join(failures))


def run_cli_failure_status_text() -> None:
    from weaver_py.cli import _failure_markup

    rendered = _failure_markup("00:08")
    ok = "失败" in rendered and "完成" not in rendered
    check("cli failure status text", ok)


def run_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "weaver_py.cli", "--help"],
        cwd=ROOT,
        env=runtime_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    check("cli help", result.returncode == 0 and "Weaver Python runtime" in result.stdout and "--tui" not in result.stdout)


def run_cli_exit() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "weaver_py.cli", "--cwd", str(ROOT)],
        cwd=ROOT,
        env=runtime_env(),
        input="﻿/exit\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    raw_prompt_lines = [line for line in result.stdout.splitlines() if line.strip() == "❯"]
    ok = result.returncode == 0 and "Weaver" in result.stdout and "再见" in result.stdout
    ok = ok and "ctx" in result.stdout and "phase general" in result.stdout
    ok = ok and "❯ /exit" in result.stdout and not raw_prompt_lines
    ok = ok and "工具开始" not in result.stdout and "工具完成" not in result.stdout
    check("cli-first default exit", ok)


def run_cli_lab_status() -> None:
    from weaver_py.cli import _status_markup

    rendered = _status_markup(
        "正在思考",
        None,
        "enum",
        "检查后台路径",
        1200,
        300,
        "·",
        "http://web-lab.local/admin/login",
        2,
    )
    ok = "▍" in rendered and "enum" in rendered and "ev:2" in rendered and "target http://web-lab.local/admin" in rendered
    check("cli lab status line", ok)


def run_transcript_renderer() -> None:
    renderer = TranscriptRenderer()
    write_start = renderer.render_event(
        AgentEvent(type="tool_start", data={"id": "write-1", "name": "Write", "input": {"file_path": str(ROOT / "x.py"), "content": "a\nb"}})
    )
    write_done = renderer.render_event(AgentEvent(type="tool_result", data={"id": "write-1", "name": "Write", "exit_code": 0, "output": "Wrote 3 characters"}))
    edit_start = renderer.render_event(
        AgentEvent(
            type="tool_start",
            data={"id": "edit-1", "name": "Edit", "input": {"file_path": str(ROOT / "x.py"), "old_string": "a", "new_string": "a\nb"}},
        )
    )
    edit_done = renderer.render_event(
        AgentEvent(type="tool_result", data={"id": "edit-1", "name": "Edit", "exit_code": 0, "output": "Edited x.py: replaced 1 occurrence(s)"})
    )
    bash_start = renderer.render_event(AgentEvent(type="tool_start", data={"id": "bash-1", "name": "Bash", "input": {"command": "rm -rf /"}}))
    bash_error = renderer.render_event(AgentEvent(type="tool_error", data={"id": "bash-1", "name": "Bash", "exit_code": 1, "output": "Command denied: dangerous"}))
    read_start = renderer.render_event(
        AgentEvent(type="tool_start", data={"id": "read-1", "name": "Read", "input": {"file_path": str(ROOT / "x.py")}})
    )
    read_done = renderer.render_event(
        AgentEvent(type="tool_result", data={"id": "read-1", "name": "Read", "exit_code": 0, "output": "line one\nline two\nline three"})
    )
    skill_start = renderer.render_event(AgentEvent(type="tool_start", data={"id": "skill-1", "name": "Skill", "input": {"skill": "demo"}}))
    skill_done = renderer.render_event(
        AgentEvent(
            type="tool_result",
            data={
                "id": "skill-1",
                "name": "Skill",
                "exit_code": 0,
                "output": "Skill: demo\nSource: project\nBase directory for this skill: D:/demo/.weaver/skills/demo\n\nUse this skill.",
            },
        )
    )
    mcp_start = renderer.render_event(AgentEvent(type="tool_start", data={"id": "mcp-1", "name": "mcp__demo__echo", "input": {"text": "hello"}}))
    mcp_done = renderer.render_event(AgentEvent(type="tool_result", data={"id": "mcp-1", "name": "mcp__demo__echo", "exit_code": 0, "output": "echo:hello"}))
    powershell_start = renderer.render_event(
        AgentEvent(type="tool_start", data={"id": "ps-1", "name": "PowerShell", "input": {"command": "Write-Output hello"}})
    )
    powershell_done = renderer.render_event(
        AgentEvent(type="tool_result", data={"id": "ps-1", "name": "PowerShell", "exit_code": 0, "output": "hello"})
    )
    rendered = "\n".join(
        write_start
        + write_done
        + edit_start
        + edit_done
        + bash_start
        + bash_error
        + read_start
        + read_done
        + skill_start
        + skill_done
        + mcp_start
        + mcp_done
        + powershell_start
        + powershell_done
    )
    ok = "┃" in rendered and "Write(" in rendered and "Edit(" in rendered and "Bash(" in rendered
    ok = ok and "✗" in rendered and "Error:" in rendered and "line one" in rendered
    ok = ok and "Skill(demo)" in rendered and "Loaded skill: demo · project" in rendered and "Base: D:/demo/.weaver/skills/demo" in rendered
    ok = ok and "MCP demo.echo" in rendered and "MCP demo.echo returned" in rendered
    ok = ok and "PowerShell(" in rendered
    check("transcript renderer", ok)


def run_security_state() -> None:
    context = SecurityContext()
    check("security default mode", context.mode == "ctf_lab" and context.phase == "general")
    context.set_target("http://web-lab.local")
    context.update_phase("enum", 0.87, "发现 Web 目录枚举线索", "检查 /admin")
    context.set_next_action("检查 /admin 的认证逻辑")
    check(
        "security context update",
        context.target == "http://web-lab.local"
        and context.phase == "enum"
        and context.phase_confidence == 0.87
        and context.next_action == "检查 /admin 的认证逻辑",
    )
    evidence = EvidenceStore()
    note = evidence.add_note("登录页返回 debug header", phase=context.phase)
    finding = evidence.add(kind="finding", title="/admin exposed", source="Bash(ffuf)", summary="目录枚举发现 /admin", phase=context.phase)
    rendered = "\n".join(evidence.render_lines())
    check(
        "evidence store",
        evidence.count == 2
        and note.kind == "note"
        and finding.title == "/admin exposed"
        and "登录页返回 debug header" in rendered
        and "/admin exposed" in rendered,
    )
    writeup = build_writeup(context, evidence)
    writeup_ok = "# Challenge" in writeup and "# Evidence" in writeup and "http://web-lab.local" in writeup and "/admin exposed" in writeup
    check("ctf writeup builder", writeup_ok)

    session = WeaverSession(ROOT)
    session.security.set_target("http://session-target.local")
    session.evidence.add_note("session note", phase="enum")
    session.update_from_event(
        AgentEvent(
            type="phase_update",
            data={"phase": "enum", "confidence": 0.9, "reason": "目录枚举", "current_task": "检查后台路径"},
        )
    )
    status = session.status_plain()
    session_ok = "target=http://session-target.local" in status and "evidence=1" in status and session.security.phase == "enum"
    check("session security state", session_ok)

    session.update_from_event(
        AgentEvent(
            type="phase_update",
            data={"phase": "invalid-phase", "confidence": 3.0, "reason": "异常 phase", "current_task": "异常任务"},
        )
    )
    normalized_ok = (
        session.current_phase == "general"
        and session.security.phase == "general"
        and session.phase_confidence == 1.0
        and session.security.phase_confidence == 1.0
    )
    check("session security normalized phase", normalized_ok)

    session.clear()
    clear_ok = session.security.target == "" and session.evidence.count == 0 and session.security.phase == "general"
    check("session security clear", clear_ok)

    command_session = WeaverSession(ROOT)
    target_result = handle_command(command_session, "/target http://cmd-target.local")
    note_result = handle_command(command_session, "/note 发现 /admin")
    evidence_result = handle_command(command_session, "/evidence")
    writeup_result = handle_command(command_session, "/writeup")
    command_ok = (
        target_result.handled
        and "Target 已设置" in target_result.message
        and command_session.security.target == "http://cmd-target.local"
        and note_result.handled
        and command_session.evidence.count == 1
        and evidence_result.handled
        and "/admin" in evidence_result.message
        and writeup_result.handled
        and "# Challenge" in writeup_result.message
    )
    check("ctf lab commands", command_ok)

    upper_target = handle_command(command_session, "/TARGET http://upper-target.local")
    upper_note = handle_command(command_session, "/NOTE 大写命令 note")
    empty_target = handle_command(command_session, "/target")
    before_empty_note_count = command_session.evidence.count
    empty_note = handle_command(command_session, "/note")
    command_edge_ok = (
        upper_target.handled
        and command_session.security.target == "http://upper-target.local"
        and upper_note.handled
        and command_session.evidence.items[-1].title == "大写命令 note"
        and empty_target.handled
        and empty_target.is_error
        and command_session.security.target == "http://upper-target.local"
        and empty_note.handled
        and empty_note.is_error
        and command_session.evidence.count == before_empty_note_count
    )
    check("ctf lab command edges", command_edge_ok)


async def run_report_command() -> None:
    session = WeaverSession(ROOT)
    session.security.set_target("http://report-target.local")
    session.evidence.add(kind="finding", title="report evidence", source="manual", summary="报告 smoke 证据", phase="enum")
    session.conversation.add_user_text("report smoke user")
    session.conversation.add_assistant_blocks([{"type": "text", "text": "report smoke assistant"}])
    result = handle_command(session, "/report")
    report_text = result.report_path.read_text(encoding="utf-8") if result.report_path else ""
    ok = (
        result.report_path is not None
        and result.report_path.exists()
        and "Weaver Session Report" in report_text
        and "http://report-target.local" in report_text
        and "report evidence" in report_text
    )
    check("session report command", ok)

    exit_session = WeaverSession(ROOT)
    exit_session.conversation.add_user_text("exit report smoke user")
    exit_session.conversation.add_assistant_blocks([{"type": "text", "text": "exit report smoke assistant"}])
    exit_result = handle_command(exit_session, "/exit")
    exit_ok = exit_result.exit_requested and exit_result.report_path is not None and exit_result.report_path.exists()
    check("normal exit report", exit_ok)


async def run_tools() -> None:
    audit_path = ROOT / ".weaver" / "audit" / "smoke-tools.jsonl"
    registry = build_default_registry(ROOT, audit_name="smoke-tools.jsonl")

    glob_result = await registry.execute("Glob", {"pattern": "src/weaver_py/**/*.py", "path": str(ROOT)})
    check("glob tool", glob_result.exit_code == 0 and "weaver_py" in glob_result.output)

    read_result = await registry.execute("Read", {"file_path": str(ROOT / "src" / "weaver_py" / "config.py"), "limit": 2})
    check("read tool", read_result.exit_code == 0 and "from __future__" in read_result.output)

    write_path = ROOT / ".weaver" / "audit" / "smoke-write.txt"
    write_result = await registry.execute("Write", {"file_path": str(write_path), "content": "alpha beta"})
    check("write tool", write_result.exit_code == 0 and write_path.read_text(encoding="utf-8") == "alpha beta")

    edit_result = await registry.execute(
        "Edit",
        {"file_path": str(write_path), "old_string": "beta", "new_string": "gamma"},
    )
    check("edit tool", edit_result.exit_code == 0 and write_path.read_text(encoding="utf-8") == "alpha gamma")

    bash_result = await registry.execute("Bash", {"command": f"{sys.executable} --version"})
    check("bash tool", bash_result.exit_code == 0 and "Python" in bash_result.output)

    if sys.platform == "win32":
        format_table_result = await registry.execute(
            "PowerShell",
            {"command": "Get-Date | Format-Table -AutoSize"},
        )
        check("powershell format-table allowed", format_table_result.exit_code == 0)

    denied_result = await registry.execute("Bash", {"command": "rm -rf /"})
    check("bash safety deny", denied_result.is_error and "Command denied" in denied_result.output)

    phase_result = await registry.execute(
        "UpdatePhase",
        {
            "phase": "recon",
            "confidence": 0.92,
            "reason": "User requested target discovery.",
            "current_task": "scope-aware reconnaissance",
        },
    )
    check("phase update tool", phase_result.exit_code == 0 and '"phase": "recon"' in phase_result.output)

    check("audit log", audit_path.exists())


async def run_capabilities() -> None:
    with tempfile.TemporaryDirectory() as raw_root:
        temp_root = Path(raw_root)
        claude_skill_dir = temp_root / ".claude" / "skills" / "cc-demo"
        claude_skill_dir.mkdir(parents=True, exist_ok=True)
        (temp_root / ".claude" / "settings.json").write_text(
            json.dumps({"mcpServers": {"from_settings": {"command": sys.executable, "args": ["server.py"]}}}),
            encoding="utf-8",
        )
        (temp_root / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"from_mcp_json": {"command": sys.executable, "args": ["server.py"]}}}),
            encoding="utf-8",
        )
        claude_skill_path = claude_skill_dir / "SKILL.md"
        claude_skill_path.write_text(
            "---\n"
            "name: cc-demo\n"
            "description: Claude Code compatible skill\n"
            "allowed-tools: [Read, Grep]\n"
            "argument-hint: target\n"
            "user-invocable: true\n"
            "paths:\n"
            "  - notes.md\n"
            "---\n\n"
            "Use $ARGUMENTS and ${ARGUMENTS}. dir=${CLAUDE_SKILL_DIR} session=${CLAUDE_SESSION_ID}\n",
            encoding="utf-8",
        )

        unmigrated = WeaverSession(temp_root, config=WeaverConfig(api_key="test-key"))
        check("project .claude skills not loaded directly", "cc-demo" not in {skill.name for skill in unmigrated.skills})
        migration = handle_command(unmigrated, "/init migrate-claude")
        check("claude project migration", migration.handled and "cc-demo" in migration.message and (temp_root / ".weaver" / "skills" / "cc-demo" / "SKILL.md").exists())

        session = WeaverSession(temp_root, config=WeaverConfig(api_key="test-key"))
        skills_result = handle_command(session, "/skills")
        skill_detail = handle_command(session, "/skills cc-demo")
        skill_tool = await session.registry.execute("Skill", {"skill": "cc-demo", "args": "demo args"})
        missing_skill = await session.registry.execute("Skill", {"skill": "missing"})
        mcp_json = json.loads((temp_root / ".mcp.json").read_text(encoding="utf-8"))
        ok = skills_result.handled and "Project skills" in skills_result.message and "cc-demo" in skills_result.message
        ok = ok and "allowed_tools=Read, Grep" in skill_detail.message and "argument-hint" in skill_detail.message
        ok = ok and skill_tool.exit_code == 0 and "demo args and demo args" in skill_tool.output
        ok = ok and "Base directory for this skill" in skill_tool.output and session.session_id in skill_tool.output and missing_skill.is_error
        ok = ok and "from_settings" in mcp_json.get("mcpServers", {}) and "from_mcp_json" in mcp_json.get("mcpServers", {})
        check("skills subsystem", ok)

        direct_root = temp_root / "direct-mcp"
        (direct_root / ".weaver").mkdir(parents=True, exist_ok=True)
        (direct_root / ".weaver" / "settings.json").write_text(
            json.dumps({"apiKey": "test-key", "mcpServers": {"shared": {"command": "settings-command"}}}),
            encoding="utf-8",
        )
        (direct_root / ".mcp.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "shared": {"command": sys.executable, "args": ["shared.py"]},
                        "direct_only": {"command": sys.executable, "args": ["direct.py"]},
                    }
                }
            ),
            encoding="utf-8",
        )
        direct_config = load_config(direct_root)
        direct_ok = direct_config.mcp_servers["shared"].command == sys.executable and "direct_only" in direct_config.mcp_servers
        check("direct .mcp.json runtime config", direct_ok)

        fake_server = temp_root / ".weaver" / "audit" / "fake_mcp_server.py"
        fake_server.parent.mkdir(parents=True, exist_ok=True)
        fake_server.write_text(
            "import json, sys\n"
            "for line in sys.stdin:\n"
            "    msg=json.loads(line)\n"
            "    method=msg.get('method')\n"
            "    if 'id' not in msg:\n"
            "        continue\n"
            "    if method=='initialize':\n"
            "        result={'protocolVersion':'2024-11-05','capabilities':{},'serverInfo':{'name':'fake','version':'1'}}\n"
            "    elif method=='tools/list':\n"
            "        result={'tools':[{'name':'echo','description':'Echo text','inputSchema':{'type':'object','properties':{'text':{'type':'string'}}}}]}\n"
            "    elif method=='tools/call':\n"
            "        args=msg.get('params',{}).get('arguments',{})\n"
            "        result={'content':[{'type':'text','text':'echo:'+str(args.get('text',''))}]}\n"
            "    else:\n"
            "        result={}\n"
            "    print(json.dumps({'jsonrpc':'2.0','id':msg['id'],'result':result}), flush=True)\n",
            encoding="utf-8",
        )
        config = WeaverConfig(api_key="test-key", mcp_servers={"demo": McpServerConfig(command=sys.executable, args=[str(fake_server)])})
        mcp_session = WeaverSession(temp_root, config=config)
        await mcp_session.reload_mcp()
        mcp_list = handle_command(mcp_session, "/mcp")
        mcp_detail = handle_command(mcp_session, "/mcp demo")
        mcp_result = await mcp_session.registry.execute("mcp__demo__echo", {"text": "hello"})
        await mcp_session.mcp.shutdown()
        ok = "connected" in mcp_list.message and "mcp__demo__echo" in mcp_detail.message
        ok = ok and mcp_result.exit_code == 0 and "echo:hello" in mcp_result.output
        check("stdio mcp subsystem", ok)

        permissions = handle_command(session, "/permissions")
        init = handle_command(session, "/init")
        check("capability commands", "权限" in permissions.message and ".weaver/skills" in init.message)


async def run_tui() -> None:
    from weaver_py.tui import WeaverTuiApp

    app = WeaverTuiApp(ROOT)
    async with app.run_test() as pilot:
        await pilot.pause()
        input_box = app.query_one("#input")
        messages = app.query_one("#messages")
        ok = app.engine is not None and input_box.disabled is False and messages.__class__.__name__ == "VerticalScroll"
        check("textual tui", ok)

        await app._append_assistant_text("A")
        await app._append_assistant_text("B")
        combined_ok = app._assistant_widget is not None and "".join(app._current_assistant) == "AB"
        check("tui streaming message merge", combined_ok)

        await app.handle_agent_event(
            AgentEvent(
                type="phase_update",
                data={
                    "phase": "enum",
                    "confidence": 0.88,
                    "reason": "Services are known; enumerate details.",
                    "current_task": "service enumeration",
                },
            )
        )
        phase_ok = app.current_phase == "enum" and app.current_task == "service enumeration" and app.phase_confidence == 0.88
        check("tui phase update", phase_ok)

        input_box.value = "/"
        await pilot.pause()
        menu = app.query_one("#command-menu")
        menu_ok = "visible" in menu.classes and any(name == "/status" for name, _ in app._filtered_commands)
        check("tui slash menu", menu_ok)

        await pilot.press("tab")
        await pilot.pause()
        tab_ok = input_box.value.startswith("/") and input_box.value in {"/exit", "/status", "/clear", "/help"}
        check("tui slash tab completion", tab_ok)

        app.busy = True
        app.current_task = "waiting smoke"
        app._run_started_at = __import__("time").monotonic() - 65
        app._tick()
        waiting_ok = app._elapsed_text() == "01:05"
        check("tui waiting timer", waiting_ok)
        app.busy = False
        app._run_started_at = None


def run_openai_chunk_merge() -> None:
    config = WeaverConfig(api_key="test-key", model="gpt-test", base_url="http://example.invalid")
    engine = AgentEngine(config, build_default_registry(ROOT), root=ROOT, max_tokens=128)
    merged = engine._merge_chat_chunks(
        [
            {"choices": [{"delta": {"content": "准备调用工具：", "tool_calls": [{"index": 0, "function": {"name": "Re", "arguments": "{\"file_"}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "ad", "arguments": "path\":\"README.md\"}"}}]}, "finish_reason": "tool_calls"}]},
            {"usage": {"prompt_tokens": 11, "completion_tokens": 7}, "choices": []},
        ]
    )
    message = merged["choices"][0]["message"]
    tool_call = message["tool_calls"][0]
    ok = (
        message["content"] == "准备调用工具："
        and tool_call["id"] == "call_0"
        and tool_call["type"] == "function"
        and tool_call["function"]["name"] == "Read"
        and tool_call["function"]["arguments"] == "{\"file_path\":\"README.md\"}"
        and merged["usage"]["prompt_tokens"] == 11
    )
    check("openai chunk tool_calls merge", ok)


async def run_openai_final_content_fallback() -> None:
    events: list[tuple[str, str]] = []

    async def on_event(event: AgentEvent) -> None:
        if event.type in {"text", "text_delta", "done"}:
            events.append((event.type, str(event.data.get("text") or event.data.get("stop_reason") or "")))

    config = WeaverConfig(api_key="test-key", model="gpt-test", base_url="http://example.invalid")
    engine = AgentEngine(config, build_default_registry(ROOT), event_handler=on_event, root=ROOT, max_tokens=128)

    async def fake_stream(_: dict[str, object]) -> dict[str, object]:
        return {
            "choices": [{"message": {"role": "assistant", "content": "你好，fallback 生效", "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            "_streamed_text": "",
        }

    engine._stream_chat_completion = fake_stream  # type: ignore[method-assign]
    result = await engine.ask("你好")
    ok = result == "你好，fallback 生效" and ("text", "你好，fallback 生效") in events and any(kind == "done" for kind, _ in events)
    check("openai final content fallback", ok)


async def run_chat_usage_fallback() -> None:
    config = WeaverConfig(api_key="test-key", base_url="http://example.local", model="gpt-test")
    registry = build_default_registry(ROOT)
    events: list[AgentEvent] = []
    payload_seen: dict[str, object] = {}

    async def on_event(event: AgentEvent) -> None:
        events.append(event)

    engine = AgentEngine(config, registry, event_handler=on_event, root=ROOT, max_tokens=64)

    async def fake_stream(payload: dict[str, object]) -> dict[str, object]:
        payload_seen.update(payload)
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "fallback usage ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
            "_streamed_text": "",
        }

    engine._stream_chat_completion = fake_stream  # type: ignore[method-assign]
    response = await engine.ask("hello fallback tokens")
    token_events = [event for event in events if event.type == "token_update"]
    stream_options = payload_seen.get("stream_options")
    ok = response == "fallback usage ok"
    ok = ok and isinstance(stream_options, dict) and stream_options.get("include_usage") is True
    ok = ok and bool(token_events)
    ok = ok and int(token_events[-1].data.get("input_tokens") or 0) > 0
    ok = ok and int(token_events[-1].data.get("output_tokens") or 0) > 0
    check("chat usage fallback", ok)


async def run_reasoning_content_replay() -> None:
    captured_payloads: list[dict[str, object]] = []

    config = WeaverConfig(api_key="test-key", model="gpt-test", base_url="http://example.invalid")
    engine = AgentEngine(config, build_default_registry(ROOT), root=ROOT, max_tokens=128)
    calls = {"count": 0}

    async def fake_stream(payload: dict[str, object]) -> dict[str, object]:
        captured_payloads.append(payload)
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": "call_0",
                            "type": "function",
                            "function": {"name": "Read", "arguments": "{\"file_path\":\"README.md\"}"},
                        }],
                        "reasoning_content": "first-pass reasoning",
                    },
                    "finish_reason": "tool_calls",
                }],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6},
                "_streamed_text": "",
            }
        replayed = captured_payloads[-1]["messages"]
        assistant_messages = [item for item in replayed if isinstance(item, dict) and item.get("role") == "assistant"]
        replay_ok = bool(assistant_messages) and assistant_messages[-1].get("reasoning_content") == "first-pass reasoning"
        content = "reasoning replay ok" if replay_ok else "reasoning replay missing"
        return {
            "choices": [{"message": {"role": "assistant", "content": content, "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 13, "completion_tokens": 4},
            "_streamed_text": "",
        }

    engine._stream_chat_completion = fake_stream  # type: ignore[method-assign]
    result = await engine.ask("读取 README")
    check("reasoning content replay", result == "reasoning replay ok")

    events: list[tuple[str, str]] = []

    async def on_event(event: AgentEvent) -> None:
        if event.type in {"text", "done"}:
            events.append((event.type, str(event.data.get("text") or event.data.get("stop_reason") or "")))

    config = WeaverConfig(api_key="test-key", model="gpt-test", base_url="http://example.invalid")
    engine = AgentEngine(config, build_default_registry(ROOT), event_handler=on_event, root=ROOT, max_tokens=128)
    calls = {"count": 0}

    async def fake_stream(_: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "choices": [{"message": {"role": "assistant", "content": "", "tool_calls": []}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1},
                "_streamed_text": "",
            }
        return {
            "choices": [{"message": {"role": "assistant", "content": "已完成。", "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 2},
            "_streamed_text": "",
        }

    engine._stream_chat_completion = fake_stream  # type: ignore[method-assign]
    result = await engine.ask("执行命令")
    ok = calls["count"] == 2 and result == "已完成。" and ("text", "已完成。") in events
    check("openai empty stop retry", ok)


async def run_gateway() -> None:
    config = load_config(ROOT)
    registry = build_default_registry(ROOT)
    deltas: list[str] = []

    async def on_event(event: AgentEvent) -> None:
        if event.type == "text_delta":
            deltas.append(str(event.data.get("text") or ""))

    engine = AgentEngine(config, registry, event_handler=on_event, root=ROOT, max_tokens=128)
    response = await engine.ask("只回复这几个字：Weaver smoke OK")
    joined = "".join(deltas).strip()
    ok = "Weaver smoke OK" in response and "Weaver smoke OK" in joined and len(deltas) > 0
    check("gateway streaming", ok, f"deltas={len(deltas)} model={config.model}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test Weaver Python runtime")
    parser.add_argument("--gateway", action="store_true", help="Call the configured model gateway")
    parser.add_argument("--tui", action="store_true", help="Initialize the Textual TUI in test mode")
    args = parser.parse_args()

    run_banner_smoke()
    run_retro_cli_palette()
    run_retro_banner_smoke()
    run_retro_cli_render_helpers()
    run_system_prompt_output_rules()
    run_cli_failure_status_text()
    run_shell_registry_order()
    run_shell_tool_descriptions()
    run_cli_help()
    run_cli_exit()
    run_cli_lab_status()
    run_transcript_renderer()
    run_security_state()
    await run_report_command()
    await run_tools()
    await run_capabilities()
    run_openai_chunk_merge()
    await run_openai_final_content_fallback()
    await run_chat_usage_fallback()
    await run_reasoning_content_replay()
    if args.tui:
        await run_tui()
    if args.gateway:
        await run_gateway()
    print("Smoke checks completed.")


if __name__ == "__main__":
    asyncio.run(main())
