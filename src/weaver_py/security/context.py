from __future__ import annotations

from dataclasses import dataclass

from weaver_py.phase import VALID_PHASES


@dataclass
class SecurityContext:
    mode: str = "ctf_lab"
    target: str = ""
    challenge: str = ""
    phase: str = "general"
    phase_confidence: float = 0.0
    phase_reason: str = ""
    current_task: str = ""
    next_action: str = ""

    def set_target(self, value: str) -> None:
        # Target 是安全测试里更自然的术语，这里保留英文，同时只清理首尾空白。
        self.target = value.strip()

    def set_challenge(self, value: str) -> None:
        self.challenge = value.strip()

    def set_next_action(self, value: str) -> None:
        self.next_action = value.strip()

    def update_phase(self, phase: str, confidence: float, reason: str, current_task: str) -> None:
        # 模型或工具可能返回不在枚举里的 phase；这里回落到 general，避免 UI 和 report 崩溃。
        self.phase = phase if phase in VALID_PHASES else "general"
        self.phase_confidence = max(0.0, min(float(confidence), 1.0))
        self.phase_reason = reason.strip()
        self.current_task = current_task.strip()

    def clear(self) -> None:
        self.target = ""
        self.challenge = ""
        self.phase = "general"
        self.phase_confidence = 0.0
        self.phase_reason = ""
        self.current_task = ""
        self.next_action = ""

    def summary_line(self, evidence_count: int = 0) -> str:
        target = self.target or "未设置"
        return f"Lab {self.mode} · Phase {self.phase} · Evidence {evidence_count} · Target {target}"
