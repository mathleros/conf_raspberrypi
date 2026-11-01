"""Shared vocabulary and bounds for voice plans."""

DEFAULT_MOVE_DURATION_SEC = 1.0
DEFAULT_TURN_ANGLE_DEG = 90.0
PLAN_INTENT_SYNONYMS = {
    "contourner_obstacle": "contour_obstacle",
    "contourne_obstacle": "contour_obstacle",
    "avoid": "avoid_obstacle",
    "find_object": "search_and_approach_object",
    "search_object": "search_and_approach_object",
    "detect_object": "search_and_approach_object",
    "approach_object": "search_and_approach_object",
    "follow": "follow_object",
    "track": "follow_object",
    "track_object": "follow_object",
    "follow_target": "follow_object",
    "suivre": "follow_object",
    "suit": "follow_object",
    "rotate_360": "spin_360",
    "spin": "spin_360",
    "square": "move_square",
    "path": "execute_path",
    "trajectory": "execute_path",
    "trajet": "execute_path",
    "go_home": "return_to_start",
    "back_to_start": "return_to_start",
}
# Sources de plan rejetées sans repli parseur ni mouvement.
UNSUPPORTED_PLAN_SOURCES = {"llm_unsupported", "llm_ungrounded"}
OBJECT_INTENTS = {"search_and_approach_object", "follow_object"}
DEFAULT_STAND_OFF_CM = 100.0
DEFAULT_FOLLOW_DURATION_SEC = 60.0
MIN_OBJECT_DURATION_SEC = 1.0
MIN_SEARCH_TIMEOUT_SEC = 1.0
MAX_SEARCH_TIMEOUT_SEC = 120.0
HUMAN_RESUME_COMMANDS = {"reprends le suivi", "reprends suivi", "reprenez le suivi"}
