from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class McpServerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ExecBackend:
    type: Literal["local", "wsl", "ssh", "docker"] = "local"
    distro: str | None = None
    host: str | None = None
    port: int | None = None
    user: str | None = None
    auth_method: Literal["password", "key", "agent"] | None = None
    password: str | None = None
    password_helper: str | None = None
    key_file: str | None = None
    container: str | None = None


@dataclass
class WeaverConfig:
    api_key: str | None = None
    api_key_helper: str | None = None
    model: str = "claude-sonnet-4-6"
    base_url: str | None = None
    custom_headers: str | None = None
    timeout: int = 600_000
    backend: ExecBackend = field(default_factory=ExecBackend)
    reports_dir: str = "~/.weaver/reports/"
    mcp_servers: dict[str, McpServerConfig] = field(default_factory=dict)

    @property
    def timeout_seconds(self) -> float:
        return self.timeout / 1000


def _snake_case(name: str) -> str:
    out: list[str] = []
    for char in name:
        if char.isupper():
            out.append("_")
            out.append(char.lower())
        else:
            out.append(char)
    return "".join(out).lstrip("_")


def _normalize_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {_snake_case(str(k)): _normalize_keys(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_keys(v) for v in value]
    return value


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _normalize_keys(data) if isinstance(data, dict) else {}


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _backend_from_dict(value: dict[str, Any] | None) -> ExecBackend:
    if not value:
        return ExecBackend()
    return ExecBackend(
        type=value.get("type", "local"),
        distro=value.get("distro"),
        host=value.get("host"),
        port=value.get("port"),
        user=value.get("user"),
        auth_method=value.get("auth_method"),
        password=value.get("password"),
        password_helper=value.get("password_helper"),
        key_file=value.get("key_file"),
        container=value.get("container"),
    )


def _mcp_servers_from_dict(value: dict[str, Any] | None) -> dict[str, McpServerConfig]:
    if not value:
        return {}
    servers: dict[str, McpServerConfig] = {}
    for name, cfg in value.items():
        if isinstance(cfg, dict) and isinstance(cfg.get("command"), str):
            servers[name] = McpServerConfig(
                command=cfg["command"],
                args=list(cfg.get("args") or []),
                env=dict(cfg.get("env") or {}),
            )
    return servers


def _resolve_api_key(config: WeaverConfig) -> str | None:
    if config.api_key:
        return config.api_key
    if not config.api_key_helper:
        return None
    try:
        result = subprocess.run(
            config.api_key_helper,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def load_config(cwd: Path | None = None) -> WeaverConfig:
    # Weaver settings stay in .weaver/settings.json; project MCP servers can be dropped into .mcp.json.
    root = cwd or Path.cwd()
    project_path = root / ".weaver" / "settings.json"
    mcp_path = root / ".mcp.json"

    data: dict[str, Any] = {}
    data = _merge_dicts(data, _load_json(project_path))
    mcp_data = _load_json(mcp_path)
    if isinstance(mcp_data.get("mcp_servers"), dict):
        data["mcp_servers"] = _merge_dicts(dict(data.get("mcp_servers") or {}), mcp_data["mcp_servers"])

    env = os.environ
    if env.get("ANTHROPIC_API_KEY"):
        data["api_key"] = env["ANTHROPIC_API_KEY"]
    if env.get("ANTHROPIC_BASE_URL"):
        data["base_url"] = env["ANTHROPIC_BASE_URL"]
    if env.get("ANTHROPIC_MODEL"):
        data["model"] = env["ANTHROPIC_MODEL"]
    if env.get("ANTHROPIC_CUSTOM_HEADERS"):
        data["custom_headers"] = env["ANTHROPIC_CUSTOM_HEADERS"]
    if env.get("API_TIMEOUT_MS"):
        try:
            data["timeout"] = int(env["API_TIMEOUT_MS"])
        except ValueError:
            pass

    config = WeaverConfig(
        api_key=data.get("api_key"),
        api_key_helper=data.get("api_key_helper"),
        model=data.get("model", "claude-sonnet-4-6"),
        base_url=data.get("base_url"),
        custom_headers=data.get("custom_headers"),
        timeout=int(data.get("timeout", 600_000)),
        backend=_backend_from_dict(data.get("backend")),
        reports_dir=data.get("reports_dir", "~/.weaver/reports/"),
        mcp_servers=_mcp_servers_from_dict(data.get("mcp_servers")),
    )
    config.api_key = _resolve_api_key(config)
    return config
