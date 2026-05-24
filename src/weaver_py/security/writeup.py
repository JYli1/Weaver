from __future__ import annotations

from .context import SecurityContext
from .evidence import EvidenceStore


def build_writeup(context: SecurityContext, evidence: EvidenceStore) -> str:
    target = context.target or "未设置"
    challenge = context.challenge or "未命名 CTF/lab challenge"
    next_action = context.next_action or "继续根据现有 evidence 推进分析。"
    current_task = context.current_task or "暂无当前任务。"
    phase_reason = context.phase_reason or "暂无阶段判断说明。"

    lines = [
        "# Challenge",
        "",
        challenge,
        "",
        "# Target",
        "",
        target,
        "",
        "# Summary",
        "",
        f"当前模式：`{context.mode}`。当前阶段：`{context.phase}`，置信度：{context.phase_confidence:.2f}。",
        f"阶段判断：{phase_reason}",
        "",
        "# Steps",
        "",
        f"- 当前任务：{current_task}",
        f"- 下一步建议：{next_action}",
        "",
        "# Evidence",
        "",
        evidence.as_markdown(),
        "",
        "# Solution",
        "",
        "根据上面的 evidence 继续补充完整利用路径或解题步骤。",
        "",
        "# Flag / Result",
        "",
        "暂未记录 flag 或最终结果。",
        "",
        "# Lessons Learned",
        "",
        "- 记录本题关键思路、误区和可复用技巧。",
    ]
    return "\n".join(lines).rstrip() + "\n"
