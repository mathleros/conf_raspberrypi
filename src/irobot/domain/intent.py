"""Domain model for a natural-language robot intent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from irobot.domain.perception import PerceptionTarget


@dataclass
class Intent:
    """Représente une intention robotique structurée."""

    name: str
    target: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""

    @property
    def perception_target(self) -> PerceptionTarget | None:
        """Return the closed semantic target represented by this intent."""
        return PerceptionTarget.from_value(
            self.parameters.get("target_object") or self.target,
        )
