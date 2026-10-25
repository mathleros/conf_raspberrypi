# Guide de Correction Rétroactif — Audit V2 : Priorité P1 (Pipeline Caméra Live Threadé)

**Origine :** Audit Architecture & Qualité V2  
**Gravité :** Critique (P1)  
**Fichier créé :** `src/irobot/hardware/camera/camera_live_pipeline.py`  
**Objectif :** Connecter la caméra réelle Picamera2 à l'interface `ObjectPerceptionPipeline` dans un thread indépendant.

---

## 1. Description du Problème

Dans la version V1, `SimulatedObjectPerception` simulait des détections pour les tests, mais aucun adaptateur n'exécutait `color_detector.py` en continu pour alimenter le robot physique. En conditions réelles, `perception` valait `None` et la boucle fermée de `FollowTargetSkill` ne pouvait pas s'activer.

---

## 2. Code à Écrire

Création de `src/irobot/hardware/camera/camera_live_pipeline.py` :

```python
[+] class CameraLivePerceptionPipeline(ObjectPerceptionPipeline):
[+]     def __init__(self, camera_index: int = 0, default_target: str = "red", poll_interval_s: float = 0.05):
[+]         self._last_detection: ObjectDetection | None = None
[+]         self._lock = threading.Lock()
[+]         self._stop_event = threading.Event()
[+]         self._thread = threading.Thread(target=self._capture_loop, name="camera-live-perception", daemon=True)
[+]         self._thread.start()
[+]
[+]     def _capture_loop(self) -> None:
[+]         camera = Picamera2(self.camera_index)
[+]         camera.configure(camera.create_preview_configuration())
[+]         camera.start()
[+]         while not self._stop_event.is_set():
[+]             frame = cv2.cvtColor(camera.capture_array(), cv2.COLOR_RGB2BGR)
[+]             candidates = detect_colored_objects(frame, color_name="red")
[+]             best = choose_best_result(candidates, "red", frame.shape, robotic=True)
[+]             with self._lock:
[+]                 self._last_detection = self._result_to_detection(best)
[+]             time.sleep(self.poll_interval_s)
[+]
[+]     def detect(self, *, target: str | None = None) -> ObjectDetection | None:
[+]         with self._lock:
[+]             return self._last_detection
[+]
[+]     def close(self) -> None:
[+]         self._stop_event.set()
```

---

## 3. Comment Tester ?

Vérifiez que la classe est bien reconnue et implémente `ObjectPerceptionPipeline` :
```bash
PYTHONPATH=src uv run python -c "
from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline
from irobot.interfaces.perception_pipeline import ObjectPerceptionPipeline
assert issubclass(CameraLivePerceptionPipeline, ObjectPerceptionPipeline)
print('Pipeline caméra live valide !')
"
```
