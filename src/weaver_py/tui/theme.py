from __future__ import annotations

import re

# CLI / TUI 共用主题色：
# - 基础色继续服务 Markdown、状态行和工具 transcript。
# - retro 相关颜色用于普通 CLI 的启动 banner、用户消息块和底部输入区。
# - accent_dim 保留给 CTF/lab 工具日志和旧状态行，避免主仓库已有 UI 语义丢失。
# - 颜色值保持集中管理，后续如果开放主题配置，必须同步补充中文配置说明。
PALETTE = {
    "bg": "#0B1020",
    "surface": "#111827",
    "surface_alt": "#0F172A",
    "border": "#334155",
    "border_focus": "#8B5CF6",
    "text": "#E5E7EB",
    "muted": "#94A3B8",
    "accent": "#8B5CF6",
    "accent_dim": "#64748B",
    "accent_2": "#60A5FA",
    "accent_soft": "#A78BFA",
    "cyan": "#38BDF8",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error": "#F87171",
    "amber": "#FACC15",
    "orange": "#F97316",
    "line_dim": "#475569",
    "user_bg": "#1E293B",
    "user_border": "#67E8F9",
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
