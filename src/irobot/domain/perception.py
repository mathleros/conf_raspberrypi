"""Domain types describing semantic perception targets."""

from __future__ import annotations

from enum import Enum


class PerceptionTarget(str, Enum):
    RED_BALL = "red_ball"
    YELLOW_BALL = "yellow_ball"
    ANY_BALL = "ball"
    USER_MARKER = "marker"
    FACE = "face"

    @classmethod
    def from_value(cls, value: object) -> PerceptionTarget | None:
        if value is None:
            return None
        aliases = {
            "red": cls.RED_BALL,
            "red_ball": cls.RED_BALL,
            "yellow": cls.YELLOW_BALL,
            "yellow_ball": cls.YELLOW_BALL,
            "ball": cls.ANY_BALL,
            "both": cls.ANY_BALL,
            "marker": cls.USER_MARKER,
            "me": cls.USER_MARKER,
            "face": cls.FACE,
            "human": cls.FACE,
        }
        return aliases.get(str(value).strip().lower())
