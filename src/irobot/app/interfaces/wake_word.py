from __future__ import annotations

from irobot.app.interfaces.text_normalizer import fold

DEFAULT_WAKE_WORD = "robot"


def split_wake_word(text: str, wake_word: str = DEFAULT_WAKE_WORD) -> str | None:
    """Texte original après le mot d'activation ; None si absent, chaîne vide si seul."""
    words = text.split()
    target = fold(wake_word).strip()
    for index, word in enumerate(words):
        if fold(word).strip() == target:
            return " ".join(words[index + 1:])
    return None
