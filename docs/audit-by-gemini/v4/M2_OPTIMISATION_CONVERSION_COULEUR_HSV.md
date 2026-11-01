# Guide de Correction V4 — Priorité M2 : Optimisation de la Conversion Couleur (HSV)

**Gravité :** Micro-optimisation CPU (M2)  
**Fichier cible :** `src/irobot/hardware/camera/camera_live_pipeline.py`  
**Objectif :** Éviter une conversion de couleur intermédiaire inutile `RGB → BGR → HSV` à chaque trame capturée.

---

## 1. Description du Problème

Dans `CameraLivePerceptionPipeline._capture_loop()` :
1. `Picamera2` est configurée en format RGB : `main={"size": (640, 480), "format": "RGB888"}`.
2. `frame_rgb = camera.capture_array()` retourne un tableau NumPy au format **RGB**.
3. Le code convertit actuellement `frame_rgb` en **BGR** : `frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)`.
4. Puis, dans `color_detector.detect_colored_objects(frame_bgr)`, OpenCV reconvertit immédiatement `frame_bgr` en **HSV** : `cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)`.

Passer directement de **RGB à HSV** supprime 30 conversions de format par seconde, économisant du temps de calcul CPU sur le Raspberry Pi 5.

---

## 2. Code à Modifier

Dans `src/irobot/hardware/camera/camera_live_pipeline.py`, modifiez la boucle `_capture_loop()` pour passer l'image RGB et utiliser `COLOR_RGB2HSV` :

### Repères visuels :
* `[-]` : Ligne à supprimer
* `[+]` : Ligne à ajouter
* `[u]` : Ligne modifiée

```python
    def _capture_loop(self) -> None:
        ...
        while not self._stop_event.is_set():
            frame_rgb = camera.capture_array()
[-]         frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

            results: list[str] = []
            for color in self._iter_colors_for_target(None, self.default_target):
[-]             candidates = detect_colored_objects(frame_bgr, color_name=color, debug=False)
[-]             best = choose_best_result(candidates, color, frame_bgr.shape, robotic=True)
[+]             # detect_colored_objects prend désormais en charge les frames RGB
[+]             candidates = detect_colored_objects(frame_rgb, color_name=color, is_rgb=True, debug=False)
[+]             best = choose_best_result(candidates, color, frame_rgb.shape, robotic=True)
                if best:
                    results.append(best)
```

*(Note : Dans `color_detector.py`, `detect_colored_objects` peut accepter un paramètre `is_rgb: bool = False` pour choisir `COLOR_RGB2HSV` au lieu de `COLOR_BGR2HSV`).*

---

## 3. Comment Tester ?

Vérifiez que la détection de couleur fonctionne identiquement en RGB direct :
```bash
PYTHONPATH=src uv run pytest tests/unit/test_skills_perception.py
```
*Résultat attendu :* Tous les tests de détection d'objet restent 100 % passants.
