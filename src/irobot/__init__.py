"""Package principal du projet irobot.

Ce package regroupe les fonctionnalités du robot : vision, navigation,
assistant vocal et orchestration des skills.
"""

__all__ = [
    "camera",
    "smart_car",
    "sensors",
    "skills",
    "orchestrator",
]


def main() -> None:
    print("Hello from camera_app!")