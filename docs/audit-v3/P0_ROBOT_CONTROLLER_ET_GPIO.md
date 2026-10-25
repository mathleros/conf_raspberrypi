# Guide de Correction — Priorité P0 : Encapsulation RobotController & Conflit GPIO

**Gravité :** Bloquant Critique (P0)  
**Fichier cible :** `src/irobot/interfaces/voice_runtime.py`  
**Objectif :** 
1. Empêcher la voiture de rouler indéfiniment lors des commandes à distance ou durée finie.
2. Éviter le crash `gpiozero.exc.GPIOPinInUse` au démarrage sur le Raspberry Pi.

---

## 1. Description du Problème

Dans la fonction `build_hardware_runtime()` :
1. `runtime["robot"] = SmartCar2WD(require_obstacle_sensor=False)` instancie directement le driver sans passer par l'adaptateur `RobotController`. Or, `SmartCar2WD` ne possède pas de méthode temporisée `forward_for()`, `left_for()`, etc. La classe `BaseMotionPrimitiveSkill` ne trouvant pas `command_for()`, elle appelle `forward()` brut sans durée. **Le robot démarre et ne s'arrête jamais.**
2. `SmartCar2WD` alloue déjà le capteur `self.distance_sensor = HC_SR04(trigger_pin=17, echo_pin=27)`. Juste après, `build_hardware_runtime()` instancie `runtime["sensor"] = HC_SR04()`, qui tente d'allouer une seconde fois les mêmes broches GPIO 17 et 27. **`gpiozero` lève immédiatement une exception fatale au boot.**

---

## 2. Code à Modifier

Ouvrez `src/irobot/interfaces/voice_runtime.py` et localisez la fonction `build_hardware_runtime()`.

### Repères visuels :
* `[-]` : Ligne à supprimer
* `[+]` : Ligne à ajouter
* `[u]` : Ligne modifiée

```python
def build_hardware_runtime() -> dict[str, Any]:
    """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
    runtime: dict[str, Any] = {
        "robot": None,
        "camera": None,
        "sensor": None,
        "perception": None,
    }

    if not sys.platform.startswith("linux"):
        return runtime

    try:
        from irobot.hardware.smart_car.smart_car import SmartCar2WD
[+]     from irobot.interfaces.robot_controller import RobotController

[u]     car = SmartCar2WD(require_obstacle_sensor=False)
[+]     runtime["robot"] = RobotController(car)
[+]     runtime["sensor"] = car.distance_sensor
    except Exception:
        runtime["robot"] = None
[+]     runtime["sensor"] = None

    try:
        from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline

        perception = CameraLivePerceptionPipeline()
        runtime["camera"] = perception
        runtime["perception"] = perception
    except Exception:
        runtime["camera"] = None
        runtime["perception"] = None

[-] try:
[-]     from irobot.hardware.sensors.hc_sr04 import HC_SR04
[-]     runtime["sensor"] = HC_SR04()
[-] except (Exception, SystemExit):
[-]     runtime["sensor"] = None

    return runtime
```

---

### Résultat final propre après modification :
```python
def build_hardware_runtime() -> dict[str, Any]:
    """Construit les dépendances hardware réelles quand elles sont disponibles (Linux/Pi)."""
    runtime: dict[str, Any] = {
        "robot": None,
        "camera": None,
        "sensor": None,
        "perception": None,
    }

    if not sys.platform.startswith("linux"):
        return runtime

    try:
        from irobot.hardware.smart_car.smart_car import SmartCar2WD
        from irobot.interfaces.robot_controller import RobotController

        car = SmartCar2WD(require_obstacle_sensor=False)
        runtime["robot"] = RobotController(car)
        runtime["sensor"] = car.distance_sensor
    except Exception:
        runtime["robot"] = None
        runtime["sensor"] = None

    try:
        from irobot.hardware.camera.camera_live_pipeline import CameraLivePerceptionPipeline

        perception = CameraLivePerceptionPipeline()
        runtime["camera"] = perception
        runtime["perception"] = perception
    except Exception:
        runtime["camera"] = None
        runtime["perception"] = None

    return runtime
```

---

## 3. Comment Tester ?

### Test 1 : Vérification de non-régression unitaire (sur Mac ou Linux)
```bash
uv run pytest -q tests/unit
```
*Résultat attendu :* 41 tests passés avec succès.

### Test 2 : Validation de l'encapsulation et du partage des broches
```bash
PYTHONPATH=src uv run python -c "
from irobot.interfaces.voice_runtime import build_hardware_runtime
hw = build_hardware_runtime()
print('Robot injecté :', type(hw['robot']))
print('Capteur partagé :', type(hw['sensor']))
if hw['robot'] is not None:
    assert hasattr(hw['robot'], 'forward_for'), 'ERREUR: forward_for manquant !'
    print('OK : RobotController correctement configuré.')
"
```

### Test 3 : Test réel sur Raspberry Pi
```bash
uv run voice-runtime --once --no-llm
```
*Résultat attendu :* Aucun crash `GPIOPinInUse`. Sur la consigne *"avance de 20 cm"*, le robot avance puis s'arrête net.
