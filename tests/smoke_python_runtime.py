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
from weaver_py.ui import TranscriptRenderer


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    if not ok:
        raise SystemExit(1)


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
        input="/exit\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    ok = result.returncode == 0 and "Weaver" in result.stdout and "再见" in result.stdout
    ok = ok and "工具开始" not in result.stdout and "工具完成" not in result.stdout
    check("cli-first default exit", ok)


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
    rendered = "\n".join(write_start + write_done + edit_start + edit_done + bash_start + bash_error + read_start + read_done + skill_start + skill_done + mcp_start + mcp_done)
    ok = "○" in rendered and "●" in rendered and "Write(" in rendered and "Edit(" in rendered and "Bash(" in rendered
    ok = ok and "Error:" in rendered and "line one" in rendered
    ok = ok and "Skill(demo)" in rendered and "Loaded skill: demo · project" in rendered and "Base: D:/demo/.weaver/skills/demo" in rendered
    ok = ok and "MCP demo.echo" in rendered and "MCP demo.echo returned" in rendered
    check("claude-like transcript renderer", ok)


async def run_report_command() -> None:
    session = WeaverSession(ROOT)
    session.conversation.add_user_text("report smoke user")
    session.conversation.add_assistant_blocks([{"type": "text", "text": "report smoke assistant"}])
    result = handle_command(session, "/report")
    ok = result.report_path is not None and result.report_path.exists() and "Weaver Session Report" in result.report_path.read_text(encoding="utf-8")
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

    run_cli_help()
    run_cli_exit()
    run_transcript_renderer()
    await run_report_command()
    await run_tools()
    await run_capabilities()
    if args.tui:
        await run_tui()
    if args.gateway:
        await run_gateway()
    print("Smoke checks completed.")


if __name__ == "__main__":
    asyncio.run(main())
