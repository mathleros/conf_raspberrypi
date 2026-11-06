"""Parseur de commandes d'`app2` : règles et mots-clés uniquement, sans LLM ni hardware.

    "robot avance deux secondes puis suis moi pendant dix secondes"
        -> [Command("move", "forward", 2.0), Command("follow", "human", 10.0)]
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from irobot.common.interfaces.text_normalizer import fr_numbers_to_digits

BEHAVIORS = ("move", "search", "approach", "follow")
MOVE_TARGETS = ("forward", "backward", "left", "right")
VISION_TARGETS = ("marker", "red_ball", "yellow_ball", "human")
DEFAULT_DURATION_S = 1.0
DEFAULT_WAKE_WORD = "robot"
PERSON_PREFIX = "person:"
SELF_NAME = "Moi"  # « suis moi » suit le visage de Moi.jpg

# Mots-clés (sans accents) reconnus dans la transcription Vosk française.
_BEHAVIOR_STEMS = {
    "search": ("cherch", "recherch", "trouv", "search", "find"),
    "approach": ("approch", "rapproch", "rejoin", "approach"),
    "follow": ("suis", "suit", "suiv", "poursu", "follow"),
}
_MOVE_WORDS = {
    "forward": ("avanc", "avant", "forward"),
    "backward": ("recul", "arriere", "backward"),
    "left": ("gauche", "left"),
    "right": ("droite", "right"),
}
_VISION_WORDS = {
    "red_ball": ("rouge", "red"),
    "yellow_ball": ("jaune", "yellow"),
    "marker": ("marqueur", "marker", "aruco", "tag"),
    "human": ("humain", "personne", "visage", "human"),
}
_DURATION_UNITS = frozenset({"sec", "secs", "seconde", "secondes", "second", "seconds", "min", "mins", "minute", "minutes"})
# Mots qui suivent « suis » sans être un prénom.
_NAME_STOPWORDS = frozenset({
    "robot", "le", "la", "les", "l", "un", "une", "de", "du", "des", "pendant", "durant", "pour",
    "balle", "balles", "ball", "marqueur", "marker", "aruco", "tag",
})
_CHAIN_SEPARATORS = ("puis", "ensuite", "then")


@dataclass(frozen=True)
class Command:
    behavior: str
    target: str
    duration: float = DEFAULT_DURATION_S

    def __post_init__(self) -> None:
        if self.behavior not in BEHAVIORS:
            raise ValueError(f"behavior inconnu : {self.behavior!r} ({', '.join(BEHAVIORS)}).")
        allowed = MOVE_TARGETS if self.behavior == "move" else VISION_TARGETS
        if self.behavior == "follow" and self.target.startswith(PERSON_PREFIX):
            if not self.target[len(PERSON_PREFIX):].strip():
                raise ValueError("person: attend un prénom (ex. person:Mathieu).")
        elif self.target not in allowed:
            raise ValueError(f"{self.behavior} accepte seulement : {', '.join(allowed)}.")
        if self.duration <= 0:
            raise ValueError("duration doit être > 0.")


def tokenize(text: str) -> list[str]:
    lowered = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in lowered if unicodedata.category(ch) != "Mn")
    return re.findall(r"[a-z0-9]+", fr_numbers_to_digits(stripped))


def _has_stem(tokens: list[str], stems: tuple[str, ...]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in stems)


def _first_match(tokens: list[str], table: dict[str, tuple[str, ...]]) -> str | None:
    return next((name for name, stems in table.items() if _has_stem(tokens, stems)), None)


def _spoken_duration(tokens: list[str]) -> float:
    for index, token in enumerate(tokens[:-1]):
        if not token.isdigit():
            continue
        unit = tokens[index + 1]
        if unit.startswith("sec"):
            return float(token)
        if unit.startswith("min"):
            return float(token) * 60.0
    return DEFAULT_DURATION_S


def _spoken_name(tokens: list[str]) -> str | None:
    """Premier mot après le verbe « suivre » qui n'est ni un nombre, ni une unité, ni un mot vide."""
    start = next(i for i, token in enumerate(tokens) if _has_stem([token], _BEHAVIOR_STEMS["follow"]))
    for index in range(start + 1, len(tokens)):
        token = tokens[index]
        if token.isdigit() or token in _NAME_STOPWORDS or token in _DURATION_UNITS:
            continue
        return SELF_NAME if token in ("moi", "me") else token.capitalize()
    return None


def _parse_tokens(tokens: list[str]) -> Command | None:
    duration = _spoken_duration(tokens)
    if duration <= 0:
        return None
    behavior = _first_match(tokens, _BEHAVIOR_STEMS)
    if behavior is not None:
        target = _first_match(tokens, _VISION_WORDS)
        if target is None and behavior == "follow":
            name = _spoken_name(tokens)
            target = None if name is None else PERSON_PREFIX + name
        elif target is None and "moi" in tokens:
            target = "human"
        return Command(behavior, target, duration) if target else None
    target = _first_match(tokens, _MOVE_WORDS)
    return Command("move", target, duration) if target else None


def parse_voice_command(text: str) -> Command | None:
    """Une phrase -> une Command ; None si incomplète ou ambiguë."""
    return _parse_tokens(tokenize(text))


def _split_chain(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _CHAIN_SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return segments


def parse_command_chain(text: str) -> list[Command] | None:
    """Une phrase (éventuellement « A puis B ») -> liste de Command.

    Tout ou rien : si un segment n'est pas compris, la chaîne est refusée pour ne pas
    exécuter une partie seulement des ordres.
    """
    commands = [_parse_tokens(segment) for segment in _split_chain(tokenize(text))]
    if not commands or any(command is None for command in commands):
        return None
    return commands


def split_wake_word(text: str, wake_word: str = DEFAULT_WAKE_WORD) -> str | None:
    """Texte qui suit le mot d'activation (peut être vide) ; None si le mot est absent."""
    tokens = tokenize(text)
    target = tokenize(wake_word)
    if not target or target[0] not in tokens:
        return None
    return " ".join(tokens[tokens.index(target[0]) + 1 :])
