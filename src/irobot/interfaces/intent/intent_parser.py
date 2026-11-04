"""Contract shared by intent parsers."""

from __future__ import annotations

from typing import Protocol

from irobot.domain.intent import Intent


class IntentPlanParser(Protocol):
    """Contract shared by text and LLM parsers."""

    def parse_plan(self, text: str) -> list[Intent]: ...

