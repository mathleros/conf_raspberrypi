# Guide de Correction Rétroactif — Audit V2 : Priorité P3 (Gestion Configurable du Capteur d'Obstacle)

**Origine :** Audit Architecture & Qualité V2  
**Gravité :** Exploitation & Testabilité (P3)  
**Fichier cible :** `src/irobot/hardware/smart_car/smart_car.py`  
**Objectif :** Permettre de tester les moteurs sans capteur HC-SR04 branché sans que la voiture ne refuse tout mouvement.

---

## 1. Description du Problème

Suite à la correction du Fail-Safe en V1, `check_obstacle()` renvoyait systématiquement `True` dès que `self.distance_sensor is None`.
*Conséquence :* Si un développeur voulait tester la voiture sans capteur ultrason connecté (ou sur un banc de test), la boucle `_run_motion_for` coupait immédiatement les moteurs en croyant voir un obstacle permanent.

---

## 2. Code à Modifier

Dans `src/irobot/hardware/smart_car/smart_car.py` :

### Étape A : Ajout de `require_obstacle_sensor` au constructeur
```python
    def __init__(
        self,
        in1=DEFAULT_PINS["in1"],
        in2=DEFAULT_PINS["in2"],
        in3=DEFAULT_PINS["in3"],
        in4=DEFAULT_PINS["in4"],
        ena=DEFAULT_PINS["ena"],
        enb=DEFAULT_PINS["enb"],
        obstacle_threshold_cm: float = 5.0,
        sensor_trigger_pin: int = 17,
        sensor_echo_pin: int = 27,
[+]     require_obstacle_sensor: bool = False,
    ):
        ...
[+]     self.require_obstacle_sensor = bool(require_obstacle_sensor)
```

### Étape B : Ajustement de la condition de vérification d'obstacle
```python
    def check_obstacle(self) -> bool:
        """Retourne True si un objet est détecté à moins de l seuil configuré."""
[+]     if self.distance_sensor is None and not self.require_obstacle_sensor:
[+]         return False # Capteur absent et non obligatoire : on n'interrompt pas le mouvement
        if self.distance_sensor is None:
            return True  # Capteur obligatoire mais absent : arrêt de sécurité

        try:
            distance_cm = self.distance_sensor.read_distance_cm()
        except Exception:
            return True
        if distance_cm is None:
            return True
        return distance_cm < self.obstacle_threshold_cm
```

---

## 3. Comment Tester ?

Testez la voiture sans capteur avec l'option par défaut :
```bash
PYTHONPATH=src uv run python -c "
from irobot.hardware.smart_car.smart_car import SmartCar2WD
car = SmartCar2WD(require_obstacle_sensor=False)
car.distance_sensor = None
assert car.check_obstacle() is False, 'Erreur: la voiture ne devrait pas être bloquée !'
print('Test déblocage sans capteur réussi !')
"
```
