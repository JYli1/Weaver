from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Phase = Literal["recon", "enum", "exploit", "post", "report", "general"]
VALID_PHASES: tuple[Phase, ...] = ("recon", "enum", "exploit", "post", "report", "general")


@dataclass
class PhaseState:
    phase: Phase = "general"
    confidence: float = 0.0
    reason: str = ""
    current_task: str = ""


class PhaseTracker:
    def __init__(self) -> None:
        self.state = PhaseState()

    def update(self, phase: str, confidence: float, reason: str, current_task: str) -> PhaseState:
        if phase not in VALID_PHASES:
            phase = "general"
        bounded_confidence = max(0.0, min(1.0, confidence))
        self.state = PhaseState(
            phase=phase,  # type: ignore[arg-type]
            confidence=bounded_confidence,
            reason=reason.strip(),
            current_task=current_task.strip(),
        )
        return self.state
