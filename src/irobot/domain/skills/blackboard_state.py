from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class BlackboardState(MutableMapping[str, Any]):
    """État partagé typé entre perception, planification et action."""

    active_intent: Any | None = None
    active_intent_name: str | None = None
    active_intent_parameters: dict[str, Any] = field(default_factory=dict)
    active_skill: str | None = None

    camera_ready: bool = False
    target_object: str | None = None
    last_camera_position: Any | None = None
    last_object_position: str | None = None
    last_ball_position: str | None = None
    last_object_distance_cm: float | None = None
    obstacle_detected: bool = False
    close_enough: bool = False

    motion: str | None = None
    follow_target_state: dict[str, Any] | None = None
    last_skill_result: Any | None = None

    extra: dict[str, Any] = field(default_factory=dict)

    KNOWN_FIELDS: ClassVar[set[str]] = {
        "active_intent",
        "active_intent_name",
        "active_intent_parameters",
        "active_skill",
        "camera_ready",
        "target_object",
        "last_camera_position",
        "last_object_position",
        "last_ball_position",
        "last_object_distance_cm",
        "obstacle_detected",
        "close_enough",
        "motion",
        "follow_target_state",
        "last_skill_result",
    }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "BlackboardState":
        state = cls()
        if not data:
            return state
        for key, value in data.items():
            state[key] = value
        return state

    def __getitem__(self, key: str) -> Any:
        if key in self.KNOWN_FIELDS:
            return getattr(self, key)
        return self.extra[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.KNOWN_FIELDS:
            setattr(self, key, value)
            return
        self.extra[key] = value

    def __delitem__(self, key: str) -> None:
        if key in self.KNOWN_FIELDS:
            setattr(self, key, None)
            return
        del self.extra[key]

    def __iter__(self) -> Iterator[str]:
        yield from self.KNOWN_FIELDS
        yield from self.extra

    def __len__(self) -> int:
        return len(self.KNOWN_FIELDS) + len(self.extra)

    def as_dict(self) -> dict[str, Any]:
        payload = {key: getattr(self, key) for key in self.KNOWN_FIELDS}
        payload.update(self.extra)
        return payload
