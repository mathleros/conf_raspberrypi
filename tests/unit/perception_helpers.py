from __future__ import annotations

from irobot.interfaces.perception_contracts import PerceptionTarget


def camera_target(pipeline, target: str) -> PerceptionTarget:
    semantic_target = PerceptionTarget.from_value(target)
    if semantic_target is None:
        raise ValueError(f"Unsupported test target: {target}")
    return semantic_target
