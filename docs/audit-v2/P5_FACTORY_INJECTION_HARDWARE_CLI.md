# Guide de Correction Rétroactif — Audit V2 : Priorité P5 (Factory d'Injection Matérielle CLI)

**Origine :** Audit Architecture & Qualité V2  
**Gravité :** Usabilité & Câblage Hardware (P5)  
**Fichier cible :** `src/irobot/interfaces/voice_runtime.py`  
**Objectif :** Instancier automatiquement les périphériques réels au lancement de la CLI `uv run voice-runtime` sur Linux.

---

## 1. Description du Problème

En V2, `VoiceRuntime` était instancié dans `main()` sans aucun paramètre (`robot=None, perception=None`). Exécuter la commande vocale sur le Raspberry Pi n'actionnait aucun moteur ni aucune caméra, rendant la CLI inerte par défaut en conditions réelles.

---

## 2. Code à Modifier

Dans `src/irobot/interfaces/voice_runtime.py` :

### Étape A : Définition de `build_hardware_runtime()`
```python
[+] def build_hardware_runtime() -> dict[str, Any]:
[+]     """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
[+]     runtime = {"robot": None, "camera": None, "sensor": None, "perception": None}
[+]     if not sys.platform.startswith("linux"):
[+]         return runtime
[+]     try:
[+]         from irobot.hardware.smart_car.smart_car import SmartCar2WD
[+]         from irobot.interfaces.robot_controller import RobotController
[+]         car = SmartCar2WD(require_obstacle_sensor=False)
[+]         runtime["robot"] = RobotController(car)
[+]         runtime["sensor"] = car.distance_sensor
[+]     except Exception:
[+]         pass
[+]     try:
[+]         from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline
[+]         perception = CameraLivePerceptionPipeline()
[+]         runtime["camera"] = perception
[+]         runtime["perception"] = perception
[+]     except Exception:
[+]         pass
[+]     return runtime
```

### Étape B : Injection dans `main()`
```python
def main():
    ...
    try:
[+]     hardware = build_hardware_runtime()
[u]     runtime = VoiceRuntime(
[+]         robot=hardware["robot"],
[+]         camera=hardware["camera"],
[+]         sensor=hardware["sensor"],
[+]         perception=hardware["perception"],
            input_device=args.input_device,
            use_llm=not args.no_llm,
        )
```

---

## 3. Comment Tester ?

Vérifiez que la factory retourne un dictionnaire de dépendances valide sur n'importe quel OS :
```bash
PYTHONPATH=src uv run python -c "
from irobot.interfaces.voice_runtime import build_hardware_runtime
hw = build_hardware_runtime()
assert isinstance(hw, dict)
print('Factory build_hardware_runtime testée avec succès !')
"
```
