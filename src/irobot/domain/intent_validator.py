"""Business rules for structured robot intents, independent of input wording."""

from irobot.domain.intent import Intent


class IntentValidator:
    """Validate intent names and normalized tracking targets."""

    ALLOWED_INTENTS = frozenset({
        "follow_person",
        "follow_red_ball",
        "avoid_obstacle",
        "search_and_approach_object",
        "follow_object",
        "contour_obstacle",
        "spin_360",
        "move_square",
        "return_to_start",
        "move_forward",
        "move_backward",
        "turn_left",
        "turn_right",
        "stop",
    })

    def validate(self, intent: Intent) -> bool:
        if intent.name not in self.ALLOWED_INTENTS:
            return False
        if intent.name in {"follow_red_ball", "follow_object"}:
            targets = {None, "red_ball"} if intent.name == "follow_red_ball" else {None, "red", "yellow"}
            target_object = intent.parameters.get("target_object")
            return (
                intent.target in targets
                and (
                    target_object is None
                    or (isinstance(target_object, str)
                    and target_object in {"red", "yellow", "red_ball", "yellow_ball", "marker"})
                )
            )
        return True
