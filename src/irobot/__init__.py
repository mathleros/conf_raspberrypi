"""Package principal du projet irobot.

Ce package regroupe les fonctionnalités du robot : vision, navigation,
assistant vocal et orchestration des skills.
"""

__all__ = [
    "camera",
    "orchestrator",
    "sensors",
    "skills",
    "smart_car",
]


def main() -> None:
    print("Hello from camera_app!")