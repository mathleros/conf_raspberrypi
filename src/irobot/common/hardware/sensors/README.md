# Capteur HC-SR04

`hc_sr04.py` fournit le pilote GPIO du capteur ultrasonique HC-SR04. Il mesure
la distance du premier obstacle en chronométrant le retour de l'impulsion
ultrasonore. Les broches sont configurées en numérotation BCM : TRIG sur GPIO 17
et ECHO sur GPIO 27 par défaut.

La classe `HC_SR04` expose `read_distance_cm()`, qui renvoie la distance en
centimètres ou `None` si aucune mesure valide n'est reçue dans la portée
configurée (400 cm par défaut). Les lectures sont sérialisées et une mesure
valide est réutilisée pendant 50 ms. Appelez `cleanup()` pour libérer les GPIO ;
le contexte d'utilisation via `try/finally` garantit leur fermeture.

## Broches GPIO utilisées

Le capteur utilise les broches BCM (Broadcom) du Raspberry Pi :

- TRIG → GPIO 17 (sortie, déclenche l'émission ultrasonore)
- ECHO → GPIO 27 (entrée, reçoit le signal de retour)

Les broches peuvent être modifiées avec `--trigger-pin` et `--echo-pin`.
Connectez également le GND du capteur au GND du Raspberry Pi.

## Test en ligne de commande

Sur le Raspberry Pi, avec `gpiozero` installé :

```bash
uv run hc-sr04 [--once] [--trigger-pin GPIO] [--echo-pin GPIO] \
    [--interval SECONDES] [--max-distance CM]
```

Sans `--once`, les mesures se répètent toutes les 0,5 seconde. `Ctrl+C` arrête
le test proprement.

> **Attention :** l'entrée GPIO du Raspberry Pi tolère 3,3 V au maximum. Le
> signal ECHO d'un HC-SR04 classique peut être à 5 V : utilisez un diviseur de
> tension ou un convertisseur de niveau avant de le relier au GPIO 27.
