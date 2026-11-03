# Smart Car 2WD (L298N)

Ce module fournit le pilote matériel d'une voiture 2 roues motrices (2WD) depuis
un Raspberry Pi via un pont en H L298N. Les moteurs sont commandés par les sorties
IN1–IN4 ; ENA et ENB reçoivent un signal PWM commun pour régler leur vitesse.
La logique de commande et la surveillance du HC-SR04 sont portées par
`RobotController` ; le CLI est dans `cli.py`.

Les commandes sont fournies par le point d'entrée `smart-car` :

```text
uv run smart-car {forward,backward,left,right,stop} [options]
```

## Options

| Option | Défaut | Description |
|---|---|---|
| `command` | – | `forward`, `backward`, `left`, `right` ou `stop` |
| `--speed` | `1.0` | Vitesse de `0.0` (arrêt) à `1.0` (maximum), appliquée aux deux moteurs |
| `--duration` | `-1` | Durée en secondes ; `-1` = indéfini (Ctrl+C), `0` = arrêt immédiat |
| `--obstacle-threshold-cm` | `20.0` | Arrête la voiture si le HC-SR04 mesure un objet à moins de X cm |
| `--obstacle-check-interval` | `0.2` | Intervalle (s) entre deux vérifications du capteur pendant un déplacement |

## Broches GPIO utilisées

Le script utilise les broches BCM (Broadcom) du Raspberry Pi :

- IN1 → GPIO 5
- IN2 → GPIO 6
- IN3 → GPIO 16
- IN4 → GPIO 24
- ENA → GPIO 12
- ENB → GPIO 13

Les broches sont numérotées en mode BCM, pas selon leur numéro physique sur le
connecteur 40 broches. Le GND du Raspberry Pi, du L298N et de l'alimentation
moteur doit être commun. La batterie moteur alimente le L298N, jamais les GPIO
du Raspberry Pi.

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

Le HC-SR04 utilise aussi les broches BCM suivantes :

```text
Raspberry Pi            HC-SR04
--------------------------------
GPIO 17 -> TRIG
GPIO 27 <- ECHO
5V      -> VCC
GND     -> GND
```

**Protection indispensable :** le signal ECHO d'un HC-SR04 classique peut
atteindre 5 V, alors que les GPIO du Raspberry Pi tolèrent au maximum 3,3 V.
Intercalez un diviseur de tension ou un convertisseur de niveau entre ECHO et
GPIO 27.

## Commandes disponibles

```bash
uv run smart-car forward
uv run smart-car backward
uv run smart-car left
uv run smart-car right
uv run smart-car stop
```

## Contrôle de vitesse

Le paramètre `--speed` doit être compris entre `0.0` et `1.0` :
- `0.0` = moteurs à l'arrêt
- `1.0` = vitesse maximale
La même valeur est appliquée aux deux moteurs.

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

## Détection d'obstacle

Pendant `forward`, `left` ou `right`, le HC-SR04 (TRIG GPIO 17, ECHO GPIO 27)
est vérifié à chaque intervalle configuré :
- distance strictement inférieure à `--obstacle-threshold-cm` : arrêt des moteurs
  et fin de la commande ;
- mesure absente : jusqu'à cinq lectures sont tentées ; si aucune n'est valide,
  le système s'arrête par sécurité ;
- `backward` ignore ce capteur orienté vers l'avant ; `stop` ne lance pas de
  vérification.

Le seuil par défaut est de 20 cm. Si le HC-SR04 n'est pas branché correctement,
les déplacements surveillés peuvent donc s'arrêter après des mesures invalides.

```bash
uv run smart-car forward --speed 0.5 --obstacle-threshold-cm 15
uv run smart-car forward --duration 5 --obstacle-check-interval 0.1
```

## Exemple complet

```bash
uv run smart-car forward --speed 0.8 --duration 3
uv run smart-car right --speed 0.4 --duration 1.5
uv run smart-car stop
```

## Sécurité

- Ne branche pas directement la batterie moteur sur les GPIO du Raspberry Pi.
- Ne relie pas directement la sortie ECHO 5 V du HC-SR04 à un GPIO du Pi :
  utilise un diviseur de tension ou un convertisseur de niveau.
- Vérifie que le GND du Pi et le GND du module moteur sont reliés.
- Vérifie également que le HC-SR04 et le Raspberry Pi partagent le GND.
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
