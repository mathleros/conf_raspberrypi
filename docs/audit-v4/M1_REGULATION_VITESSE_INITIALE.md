# Guide de Correction V4 — Priorité M1 : Régulation de la Vitesse Initiale

**Gravité :** Confort de roulage & Calibration (M1)  
**Fichier cible :** `src/irobot/interfaces/voice_runtime.py`  
**Objectif :** Initialiser les moteurs à 50 % de puissance PWM (`0.5`) dès l'instanciation matérielle pour correspondre à la calibration de `25.0 cm/s` et éviter les démarrages brusques.

---

## 1. Description du Problème

Dans `SmartCar2WD`, la vitesse initiale par défaut est fixée à `1.0` (100 % de puissance PWM).  
Sur une base 2WD alimentée en 6V-7.4V, 100 % de PWM propulse le robot à plus de 45-50 cm/s avec un à-coup au démarrage, alors que le fichier `runtime_calibration.toml` est configuré sur une hypothèse de `25.0 cm/s` :
```toml
# config/runtime_calibration.toml
[runtime]
cm_per_second = 25.0
```
Fixer la vitesse initiale à `0.5` dans la factory de production harmonise le déplacement physique avec les temps de trajet calculés.

---

## 2. Code à Modifier

Ouvrez `src/irobot/interfaces/voice_runtime.py` dans la fonction `build_hardware_runtime()`.

### Repères visuels :
* `[-]` : Ligne à supprimer
* `[+]` : Ligne à ajouter
* `[u]` : Ligne modifiée

```python
    try:
        from irobot.hardware.smart_car.smart_car import SmartCar2WD
        from irobot.interfaces.robot_controller import RobotController

        car = SmartCar2WD(require_obstacle_sensor=False)
[+]     car.set_speed(0.5)  # Régulation initiale à 50% conforme à la calibration de 25 cm/s
        runtime["robot"] = RobotController(car)
        runtime["sensor"] = car.distance_sensor
    except Exception:
        runtime["robot"] = None
        runtime["sensor"] = None
```

---

### Résultat final propre :
```python
    try:
        from irobot.hardware.smart_car.smart_car import SmartCar2WD
        from irobot.interfaces.robot_controller import RobotController

        car = SmartCar2WD(require_obstacle_sensor=False)
        car.set_speed(0.5)
        runtime["robot"] = RobotController(car)
        runtime["sensor"] = car.distance_sensor
    except Exception:
        runtime["robot"] = None
        runtime["sensor"] = None
```

---

## 3. Comment Tester ?

### Test unitaire sur Mac (avec mock) :
```bash
PYTHONPATH=src uv run python -c "
from unittest.mock import patch, MagicMock

with patch('sys.platform', 'linux'):
    with patch('irobot.hardware.smart_car.smart_car.SmartCar2WD') as MockCar:
        car_mock = MagicMock()
        MockCar.return_value = car_mock
        from irobot.interfaces.voice_runtime import build_hardware_runtime
        hw = build_hardware_runtime()
        car_mock.set_speed.assert_called_once_with(0.5)
        print('✅ Vitesse initiale vérifiée à 0.5 !')
"
```
