# Guide de Correction Rétroactif — Audit V1 : Priorité P2 (Mouvements Non Bloquants & Fail-Safe)

**Origine :** Audit Architecture & Qualité V1  
**Gravité :** Sécurité Physique (P2)  
**Fichiers cibles :** `src/irobot/interfaces/robot_controller.py` et `src/irobot/hardware/smart_car/smart_car.py`  
**Objectif :** Remplacer les `time.sleep()` aveugles par un polling régulier des capteurs et corriger la logique Fail-Safe en cas d'erreur de lecture.

---

## 1. Description du Problème

1. Dans `RobotController`, `forward_for()` exécutait un `time.sleep(duration_seconds)` bloquant. Si un obstacle surgissait pendant ce laps de temps, la voiture ne pouvait pas s'arrêter et percutait l'obstacle.
2. Dans `SmartCar2WD.check_obstacle()`, si le capteur renvoyait `None` (erreur ou absence d'écho), le code retournait `False` (aucun obstacle), autorisant le robot à foncer dans le mur.

---

## 2. Code à Modifier

### Étape A : `src/irobot/interfaces/robot_controller.py`
Remplacement du `time.sleep` bloquant par une boucle cadencée à 20 ms :

```python
class RobotController:
    """Adapter between robot business logic and hardware implementation."""

[+] CONTROL_LOOP_PERIOD_S = 0.02

    ...

[+] def _is_emergency_stop_requested(self) -> bool:
[+]     detectors = ("is_emergency_stop_requested", "check_emergency_stop", "stop_requested")
[+]     for name in detectors:
[+]         if hasattr(self.robot, name):
[+]             val = getattr(self.robot, name)
[+]             return bool(val() if callable(val) else val)
[+]     return False

[+] def _run_motion_for(self, start_motion, duration_seconds: float) -> None:
[+]     duration = max(0.0, float(duration_seconds))
[+]     start_motion()
[+]     if duration <= 0.0:
[+]         self.stop()
[+]         return
[+]     deadline = time.monotonic() + duration
[+]     while True:
[+]         if self._is_emergency_stop_requested() or self.check_obstacle():
[+]             self.stop()
[+]             return
[+]         remaining = deadline - time.monotonic()
[+]         if remaining <= 0.0:
[+]             break
[+]         time.sleep(min(self.CONTROL_LOOP_PERIOD_S, remaining))
[+]     self.stop()

    def forward_for(self, duration_seconds: float) -> None:
[-]     self.forward()
[-]     time.sleep(max(0.0, duration_seconds))
[-]     self.stop()
[+]     self._run_motion_for(self.forward, duration_seconds)
```

### Étape B : `src/irobot/hardware/smart_car/smart_car.py`
Correction du Fail-Safe dans `check_obstacle()` :

```python
    def check_obstacle(self) -> bool:
        if self.distance_sensor is None:
[u]         return True # Fail-safe si capteur absent ou en panne

        try:
            distance_cm = self.distance_sensor.read_distance_cm()
        except Exception:
[+]         return True # Fail-safe en cas d'exception I/O
        if distance_cm is None:
[-]         return False # DANGEREUX : faux négatif
[+]         return True  # SÉCURITÉ : absence de mesure = danger
        return distance_cm < self.obstacle_threshold_cm
```

---

## 3. Comment Tester ?

Exécutez le test unitaire simulant un obstacle en cours de route :
```bash
uv run pytest -k "test_language_controller_prioritizes_obstacle_stop"
```
*Résultat attendu :* Le statut renvoyé est `aborted` avec la raison `obstacle prioritized`.
