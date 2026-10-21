# Module Smart Car

Ce module pilote une voiture 2 roues motrices (2WD) sur Raspberry Pi via un pont H-bridge L298N.

Il permet de :
- avancer
- reculer
- tourner à gauche / à droite
- arrêter les moteurs
- régler la vitesse via PWM sur les pins ENA / ENB

Commande principale :

```bash
uv run smart-car <command> [--speed 0.0-1.0] [--duration N]
```

## Broches GPIO utilisées

Le script utilise les broches BCM (Broadcom) du Raspberry Pi :

- IN1 → GPIO 5
- IN2 → GPIO 6
- IN3 → GPIO 16
- IN4 → GPIO 24
- ENA → GPIO 12
- ENB → GPIO 13

Important :
- les GPIO sont numérotés en mode BCM, pas en numéro de broche physique
- le GND du Raspberry Pi doit être relié au GND du module L298N
- la batterie moteur doit être connectée au module L298N, pas directement sur le Pi

## Exemple de câblage

```text
Raspberry Pi            L298N / moteur
--------------------------------------
GPIO 5  -> IN1
GPIO 6  -> IN2
GPIO 16 -> IN3
GPIO 24 -> IN4
GPIO 12 -> ENA
GPIO 13 -> ENB
GND     -> GND du module

Batterie moteur + -> alimentation du module
Batterie moteur - -> GND du module
```

## Commandes disponibles

```bash
uv run smart-car forward
uv run smart-car backward
uv run smart-car left
uv run smart-car right
uv run smart-car stop
```

## Contrôle de vitesse

Le paramètre `--speed` est compris entre `0.0` et `1.0` :
- `0.0` = arrêt / vitesse minimale
- `1.0` = vitesse maximale

Exemples :

```bash
uv run smart-car forward --speed 0.5
uv run smart-car left --speed 0.3
uv run smart-car right --speed 1.0
```

## Durée d'exécution

Le paramètre `--duration` permet de limiter le temps d'action :
- `--duration 2` : avance pendant 2 secondes puis stop
- `--duration 0` : arrêt immédiat
- sans `--duration` : mouvement continu jusqu'à Ctrl+C

Exemples :

```bash
uv run smart-car forward --speed 0.7 --duration 2
uv run smart-car backward --speed 0.6
uv run smart-car stop
```

## Exemple complet

```bash
uv run smart-car forward --speed 0.8 --duration 3
uv run smart-car right --speed 0.4 --duration 1.5
uv run smart-car stop
```

## Sécurité

- Ne branche pas directement la batterie moteur sur les GPIO du Raspberry Pi.
- Vérifie que le GND du Pi et le GND du module moteur sont reliés.
- Utilise une alimentation adaptée aux moteurs.
- Déconnecte la batterie avant de modifier les câbles.

## Dépannage

### La voiture ne bouge pas

Vérifie :
- alimentation moteur présente
- GND Pi connecté au GND du L298N
- broches GPIO correctes
- ENA / ENB correctement câblés
- tu n'utilises pas les mauvais numéros BCM

### Une roue tourne seule

Cela indique généralement un problème de masse commune ou un câblage incohérent.

Vérifie :
- le GND du Pi est bien relié au GND du module L298N
- la batterie moteur est bien branchée au module, pas sur le Pi
- les sorties moteur ne sont pas en court-circuit

### Le script ne démarre pas

Vérifie que `gpiozero` est bien installé :

```bash
python3 -c "import gpiozero; print(gpiozero.__version__)"
```

Et si besoin :

```bash
uv sync --project .
```

## Notes de conception

Le moteur est contrôlé avec :
- des sorties logiques `DigitalOutputDevice` pour la direction
- des sorties PWM `PWMOutputDevice` pour la vitesse sur ENA / ENB

La logique interne est simple :
- direction = commande logique IN1/IN2 / IN3/IN4
- vitesse = niveau PWM sur ENA / ENB

Le script est prévu pour des tests de moteur et des démonstrations de pilotage simple sur Raspberry Pi.
