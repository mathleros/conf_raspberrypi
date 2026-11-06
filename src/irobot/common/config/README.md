# Configuration iRobot

Les paramètres du robot sont dans [runtime_settings.toml](runtime_settings.toml).
Ils sont chargés par `settings.py` au démarrage.

- `[runtime]` : vitesses et délais d’exécution.
- `[limits]` : bornes des déplacements, durées et plans.
- `[camera]` : dimensions de capture et d’image orientée, seuil de bord de suivi (`edge_offset_threshold`), focale pour les
  distances, correction d’image et détection de visages.
- `[human_follow]` : paramètres temporels du suivi humain.

Modifie les valeurs dans le TOML plutôt que les valeurs par défaut de `settings.py`.
Les clés absentes utilisent les valeurs par défaut ; une clé inconnue, une section
mal formée ou une valeur du mauvais type provoque une erreur au chargement.
`face_model_path` peut être absolu ou relatif à `runtime_settings.toml`.
Pour recalibrer la focale, lance `uv run calibrate-distance --known-distance-cm 100`,
puis reporte le résultat `focal_px` dans `[camera]`.

Les paramètres du client LLM sont séparés dans `llm_settings.py` et configurés
par les variables d’environnement `LLM_*`.
