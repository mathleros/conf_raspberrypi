from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillContext:
    """Contexte partagé disponible à l'exécution d'une skill.

    Il contient l'instance du robot, les composants sensoriels et des données
    d'état mutables partagées entre skills.
    """

    robot: Any | None = None
    camera: Any | None = None
    sensor: Any | None = None
    perception: Any | None = None
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Résultat standardisé produit par une skill.

    status : succès / échec / en cours / timeout
    message : libellé lisible pour logs ou debug
    data : payload métier utile à l'orchestrateur
    confidence : score entre 0.0 et 1.0
    next_action : nom de la skill suivante recommandée
    """

    status: str = "success"
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    next_action: str | None = None


class Skill(ABC):
    """Contrat de base pour toute skill du robot.

    Une skill ne pilote pas directement le système de manière libre : elle
    reçoit un contexte partagé, valide les préconditions, puis retourne un
    résultat standardisé exploitable par un orchestrateur.
    """

    name: str = "skill"
    description: str = "Skill générique"

    @abstractmethod
    def execute(self, context: SkillContext) -> SkillResult:
        """Exécute la skill et retourne un résultat structuré."""
        raise NotImplementedError

    def validate(self, context: SkillContext) -> bool:
        """Vérifie si la skill peut être exécutée dans le contexte courant."""
        return True

    def __str__(self) -> str:
        return self.name
