from __future__ import annotations

import json

from weaver_py.phase import PhaseTracker, VALID_PHASES

from .base import BaseTool, ToolResult


class UpdatePhaseTool(BaseTool):
    name = "UpdatePhase"
    description = "Update Weaver's current pentest workflow phase with structured metadata."
    input_schema = {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "enum": list(VALID_PHASES),
                "description": "Current workflow phase: recon, enum, exploit, post, report, or general.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence from 0.0 to 1.0 that this phase is correct.",
            },
            "reason": {
                "type": "string",
                "description": "Short reason for the phase selection or transition.",
            },
            "current_task": {
                "type": "string",
                "description": "Short label for the current task being performed.",
            },
        },
        "required": ["phase", "confidence", "reason", "current_task"],
    }

    def __init__(self, tracker: PhaseTracker | None = None) -> None:
        self.tracker = tracker or PhaseTracker()

    async def execute(self, input: dict[str, object]) -> ToolResult:
        phase = str(input.get("phase") or "general")
        try:
            confidence = float(input.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        reason = str(input.get("reason") or "")
        current_task = str(input.get("current_task") or "")
        state = self.tracker.update(phase, confidence, reason, current_task)
        return ToolResult(
            json.dumps(
                {
                    "phase": state.phase,
                    "confidence": state.confidence,
                    "reason": state.reason,
                    "current_task": state.current_task,
                },
                ensure_ascii=False,
            ),
            0,
        )
