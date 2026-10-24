from __future__ import annotations

"""Machine d'états d'une mission robotique.

Cette machine d'états constitue le premier niveau de supervision logicielle.
Elle formalise la progression d'une mission sous forme de phases explicites :
idle -> planning -> executing -> success / failed / aborted.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MissionState:
    """État courant d'une mission."""

    phase: str = "idle"
    intent: str | None = None
    target: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MissionStateMachine:
    """Machine d'états pour orchestrer une mission robotique."""

    VALID_PHASES = {"idle", "planning", "executing", "success", "failed", "aborted"}

    def __init__(self):
        self.state = MissionState()

    def start(self, intent: str, target: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        if not intent or not intent.strip():
            self.state.phase = "failed"
            self.state.last_error = f"Intent inconnue : {intent}"
            return

        self.state.phase = "planning"
        self.state.intent = intent
        self.state.target = target
        self.state.metadata = metadata or {}

    def begin_execution(self) -> None:
        self.state.phase = "executing"

    def succeed(self) -> None:
        self.state.phase = "success"

    def fail(self, error: str) -> None:
        self.state.phase = "failed"
        self.state.last_error = error
        self.state.metadata["failed_at"] = self.state.metadata.get("step_index")

    def abort(self, reason: str) -> None:
        self.state.phase = "aborted"
        self.state.last_error = reason
        self.state.metadata["aborted_at"] = self.state.metadata.get("step_index")

    def reset(self) -> None:
        self.state = MissionState()

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase": self.state.phase,
            "intent": self.state.intent,
            "target": self.state.target,
            "last_error": self.state.last_error,
            "metadata": self.state.metadata,
        }
