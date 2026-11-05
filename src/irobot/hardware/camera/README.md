# Caméra et perception

Ce package fournit la perception visuelle du robot à partir de la caméra
Picamera2. Le pipeline live acquiert les images dans un thread dédié, les
oriente, applique le traitement d'image commun, puis ne lance que le détecteur
correspondant à la cible demandée. Il renvoie une `ObjectDetection` ou `None` ;
il ne commande pas les moteurs et n'enregistre pas les images.

## Modules

| Module | Responsabilité |
|---|---|
| `camera_live_perception_pipeline.py` | Pipeline Picamera2, thread de capture, sélection de la cible, amélioration des images et lissage exponentiel des distances. Contient aussi `ExponentialSmoother`. |
| `frame_enhancer.py` | Correction optionnelle du contre-jour (CLAHE sur le canal L en LAB) et configuration de la compensation d'exposition Picamera2. |
| `detector/target_detector.py` | Aiguillage d'une image vers le détecteur de la cible demandée ; charge le détecteur de visages au premier besoin. |
| `detector/color_detector.py` | Détection des balles rouges et jaunes et estimation de leur distance visuelle. |
| `detector/aruco_detector.py` | Détection et estimation de pose d'un marqueur ArUco. |
| `detector/face_detector.py` | Détection YuNet d'un visage, avec mémoire temporaire de la dernière détection. |
| `detector/distance_estimator.py` | Estimation de distance selon le modèle du sténopé. |
| `detector/base_detector.py` | Types et abstractions communs aux détecteurs. |

Le contrat des cibles et des résultats (`PerceptionTarget`,
`TargetFrameDetector`, `ObjectDetection`) est défini dans
[`interfaces/perception_contracts.py`](../../interfaces/perception_contracts.py).

## Utilisation dans le runtime

Le runtime matériel construit `CameraLivePerceptionPipeline` et l'expose sous
le contrat `ObjectPerceptionPipeline`. Un consommateur demande une cible avec
`detect(*, target=...)` :

```python
from irobot.hardware.camera.camera_live_perception_pipeline import CameraLivePerceptionPipeline
from irobot.domain.perception import PerceptionTarget

camera = CameraLivePerceptionPipeline()
try:
    detection = camera.detect(target=PerceptionTarget.YELLOW_BALL)
finally:
    camera.close()
```

Les cibles sont `RED_BALL`, `YELLOW_BALL`, `ANY_BALL`, `USER_MARKER` et `FACE`.
Les alias textuels sont convertis par `PerceptionTarget.from_value` : `ball`/`balle`
vers les balles, `marker`/`tag` vers ArUco, `face`/`human`/`moi`/`personne`/`humain`/`visage`
vers le visage. Le résultat contient notamment la position
(`left`, `center`, `right` ou `UNKNOWN`), la confiance, la boîte éventuelle et
les distances en centimètres. Une absence de cible dans l'image retourne `None`.

Le pipeline utilise par défaut la caméra 0 et démarre la capture à sa
construction. `autostart=False` permet de créer l'objet sans démarrer le thread,
notamment pour les tests. `close()` demande l'arrêt et attend le thread ; si un
délai explicite expire avant son arrêt, une `TimeoutError` est levée. Picamera2
peut être absent sur les plateformes sans Raspberry Pi : dans ce cas, le
pipeline journalise l'indisponibilité et termine son thread. L'injection d'un
`TargetFrameDetector` permet de tester le pipeline sans utiliser les détecteurs
par défaut.

## Réglages et limites

Les paramètres caméra sont lus depuis la configuration du runtime, section
`[camera]` de `runtime_settings.toml` :

- `capture_size_px` configure la capture ; l'image est tournée de 90° dans le
  sens horaire avant détection.
- `exposure_value` règle la compensation d'exposition si le contrôle
  Picamera2 `ExposureValue` est disponible.
- `clahe_enabled` et `clahe_clip_limit` activent et règlent la correction locale
  du contraste.
- `ball_diameter_cm` et `focal_px` configurent les estimations visuelles.
- L'identité du marqueur, les paramètres de YuNet et la taille de l'image
  orientée règlent leurs détecteurs respectifs.

La distance d'une balle est estimée à partir de son diamètre apparent et de son
diamètre réel configuré. Celle d'un visage est indicative et dépend de la
largeur réelle du visage. La distance d'un marqueur est obtenue par pose et
dépend de la taille physique connue du marqueur et de la calibration caméra.
Ces estimations ne sont pas des mesures de sécurité : elles doivent être
calibrées et vérifiées sur le robot. Le capteur ultrason reste distinct et
n'est pas fusionné avec la distance de la cible visuelle.

Le pipeline applique un filtre exponentiel aux distances. Son coefficient
`smoothing_alpha` est compris dans `]0, 1]` et vaut `0.4` par défaut. Le filtre
est réinitialisé lorsqu'une cible change ou qu'une détection est perdue.

Pour le modèle YuNet et les détails de réglage, consulter le
[guide du package](../../README.md#détection-de-visages) et la documentation
du [diagnostic vision](../../README.md#diagnostic-vision).

## Diagnostic et tests

Sur un Raspberry Pi avec une caméra compatible et un affichage X11 :

```bash
uv run vision-detect-live
```

Le diagnostic affiche les détections ArUco, visage et balles rouge/jaune sans
piloter les moteurs ni enregistrer les images. `uv run vision-detect-live
--preview-only` affiche le flux corrigé sans exécuter de détecteurs. Quitter
avec `q` ou Ctrl+C.

Depuis la racine du projet, les tests unitaires associés à la caméra peuvent
être lancés avec :

```bash
uv run pytest -q tests/unit/test_distance_estimator.py \
  tests/unit/test_camera_aruco.py tests/unit/test_face_detector.py \
  tests/unit/test_frame_enhancer.py tests/unit/test_camera_color_format.py \
  tests/unit/test_camera_pipeline_shutdown.py tests/unit/test_vision_diagnostic.py
```
