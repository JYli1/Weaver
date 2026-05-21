from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Decision = Literal["allow", "ask", "deny"]


@dataclass(frozen=True)
class CommandDecision:
    decision: Decision
    reason: str


class CommandPolicy:
    def __init__(self) -> None:
        self._deny_patterns = [
            (re.compile(r"\brm\s+-rf\s+(/|~|\*|\.)"), "refuses destructive recursive deletion"),
            (re.compile(r"\b(format|mkfs|fdisk|diskpart)\b", re.I), "refuses disk destructive commands"),
            (re.compile(r"\b(dd)\b.*\bof=/dev/", re.I), "refuses raw disk writes"),
            (re.compile(r"\b(chmod\s+777|icacls\b.*Everyone)", re.I), "refuses broad permission weakening"),
            (re.compile(r"\b(fork\s*bomb|:\(\)\s*\{\s*:\|:)\b", re.I), "refuses denial-of-service patterns"),
        ]
        self._ask_patterns = [
            (re.compile(r"\b(nmap|masscan|sqlmap|hydra|ffuf|gobuster|nikto)\b", re.I), "security tool execution requires authorization scope"),
            (re.compile(r"\b(msfconsole|metasploit|mimikatz|bloodhound|rubeus)\b", re.I), "dual-use tool execution requires explicit confirmation"),
            (re.compile(r"\b(curl|wget)\b.*\|\s*(sh|bash|python|pwsh)", re.I), "remote code execution pipeline requires confirmation"),
            (re.compile(r"\b(shutdown|reboot|halt|poweroff)\b", re.I), "system power operation requires confirmation"),
        ]
        self._read_only = re.compile(
            r"^\s*(pwd|ls|dir|whoami|id|uname|hostname|python\s+--version|python\s+-m\s+weaver_py\.cli\s+--help|git\s+status|git\s+diff|git\s+log|ripgrep|rg)\b",
            re.I,
        )

    def evaluate(self, command: str, confirmed: bool = False) -> CommandDecision:
        for pattern, reason in self._deny_patterns:
            if pattern.search(command):
                return CommandDecision("deny", reason)
        for pattern, reason in self._ask_patterns:
            if pattern.search(command):
                return CommandDecision("allow" if confirmed else "ask", reason)
        if self._read_only.search(command):
            return CommandDecision("allow", "read-only command")
        return CommandDecision("allow", "command allowed by default policy")
