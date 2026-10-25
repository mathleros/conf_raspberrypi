# Guide de Correction — Priorité P1 : Optimisation Résolution Picamera2

**Gravité :** Performance & Fluidité (P1)  
**Fichier cible :** `src/irobot/hardware/camera/camera_live_pipeline.py`  
**Objectif :** Éviter la saturation CPU du Raspberry Pi 5 et garantir un flux d'analyse OpenCV fluide à 30 images/seconde.

---

## 1. Description du Problème

Dans `CameraLivePerceptionPipeline._capture_loop()` :
Sans paramètre explicite, `create_preview_configuration()` active la résolution native maximale du capteur vidéo (ex. 2592x1944 sur caméra v1 OV5647 ou 1080p).
* **Impact :** OpenCV doit convertir en BGR, calculer les masques HSV et chercher les contours sur plus de 2 à 5 millions de pixels par frame.
* **Conséquence :** Le processeur du Pi 5 sature à 100 %, le framerate s'effondre à 2-4 fps, provoquant un retard important (lag de 300 à 500 ms) dans la détection de la balle rouge.

Une résolution de **640x480** (ou **320x240**) est largement suffisante pour segmenter une couleur et diviser la charge CPU par 10 grâce au redimensionnement matériel (ISP du Pi).

---

## 2. Code à Modifier

Ouvrez `src/irobot/hardware/camera/camera_live_pipeline.py` et localisez la méthode `_capture_loop()`.

### Repères visuels :
* `[-]` : Ligne à supprimer
* `[+]` : Ligne à ajouter
* `[u]` : Ligne modifiée

```python
    def _capture_loop(self) -> None:
        if Picamera2 is None:
            return

        camera = None
        try:
            camera = Picamera2(self.camera_index)
[-]         config = camera.create_preview_configuration()
[+]         # Configuration matérielle explicite en basse résolution 640x480 RGB
[+]         config = camera.create_preview_configuration(
[+]             main={"size": (640, 480), "format": "RGB888"}
[+]         )
            camera.configure(config)
            camera.start()
```

---

### Résultat final propre après modification :
```python
    def _capture_loop(self) -> None:
        if Picamera2 is None:
            return

        camera = None
        try:
            camera = Picamera2(self.camera_index)
            config = camera.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            camera.configure(config)
            camera.start()
```

---

## 3. Comment Tester ?

### Test 1 : Vérification de syntaxe et import (sur Mac ou Linux)
```bash
PYTHONPATH=src uv run python -c "
from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline
print('Import CameraLivePerceptionPipeline OK')
"
```

### Test 2 : Mesure de cadence réelle sur Raspberry Pi
```bash
PYTHONPATH=src uv run python -c "
import time
from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline

pipeline = CameraLivePerceptionPipeline()
time.sleep(1.0) # Laisser le temps à la caméra de démarrer

start = time.time()
frames = 0
while time.time() - start < 3.0:
    det = pipeline.detect()
    frames += 1
    time.sleep(0.02)

pipeline.close()
fps = frames / (time.time() - start)
print(f'Cadence mesurée : {fps:.1f} FPS (Objectif >= 20 FPS)')
assert fps >= 15, 'Cadence trop basse !'
"
```
*Résultat attendu :* Une fréquence stable entre 20 et 35 FPS avec une utilisation CPU inférieure à 25 %.
