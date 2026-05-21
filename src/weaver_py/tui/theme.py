from __future__ import annotations

import re

PALETTE = {
    "bg": "#0B1020",
    "surface": "#111827",
    "surface_alt": "#0F172A",
    "border": "#334155",
    "border_focus": "#8B5CF6",
    "text": "#E5E7EB",
    "muted": "#94A3B8",
    "accent": "#8B5CF6",
    "accent_2": "#60A5FA",
    "accent_soft": "#A78BFA",
    "cyan": "#38BDF8",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error": "#F87171",
}

PHASE_STYLES = {
    "recon": PALETTE["accent_2"],
    "enum": PALETTE["cyan"],
    "exploit": PALETTE["error"],
    "post": PALETTE["accent"],
    "report": PALETTE["accent_soft"],
    "general": PALETTE["text"],
}

PHASE_LABELS = {
    "recon": "侦察",
    "enum": "枚举",
    "exploit": "利用",
    "post": "后渗透",
    "report": "报告",
    "general": "通用",
}

PHASE_CLASS_NAMES = tuple(PHASE_STYLES.keys())
CONTEXT_MAX_TOKENS = 200_000


def detect_phase(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(nmap|masscan|subfinder|amass|shodan|censys|theharvester)\b", lower):
        return "recon"
    if re.search(r"\bscan\s+(port|network|subnet|host|target)", lower):
        return "recon"
    if re.search(r"\b(gobuster|ffuf|dirb|dirsearch|wfuzz|nikto|enum4linux|hydra|crackmapexec|medusa)\b", lower):
        return "enum"
    if re.search(r"\b(sqlmap|metasploit|msfconsole|msfvenom|searchsploit)\b", lower):
        return "exploit"
    if re.search(r"\b(reverse.shell|bind.shell|webshell|exploit\s+(the|this|that|a))\b", lower):
        return "exploit"
    if re.search(r"\b(mimikatz|bloodhound|rubeus|linpeas|winpeas|chisel)\b", lower):
        return "post"
    if re.search(r"\b(privilege.escalat|lateral.mov|exfiltrat)", lower):
        return "post"
    if re.search(r"\b(generate|write|create)\s+(a\s+)?(report|summary|finding)", lower):
        return "report"
    return "general"


def format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def token_style(used: int, total: int = CONTEXT_MAX_TOKENS) -> str:
    pct = used / total if total else 0
    if pct >= 0.95:
        return PALETTE["error"]
    if pct >= 0.80:
        return PALETTE["warning"]
    return PALETTE["text"]
