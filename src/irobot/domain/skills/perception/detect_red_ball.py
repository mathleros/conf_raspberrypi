"""Compatibilité legacy pour l'ancien nom de module `detect_red_ball`.

Le code source de détection est centralisé dans `detect_object.py` pour éviter
les doublons.
"""

from irobot.domain.skills.perception.detect_object import DetectObjectSkill

__all__ = ["DetectObjectSkill"]
