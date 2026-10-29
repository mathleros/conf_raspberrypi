# Campagne de non-régression bout en bout sur Raspberry Pi — après audit V6

## 1. Objectif et périmètre

Dérouler cette campagne sur le **Raspberry Pi et le robot réels**. Elle valide la chaîne :

**micro → Vosk → texte → LLM ou parseur local → validation → orchestration → moteurs**, avec caméra et HC-SR04 réels, puis arrêt effectif.

Cas de référence : « Cherche la balle jaune, approche-toi à un mètre puis suis-la pendant cinq minutes. »

Les tests Python et les scénarios simulés restent nécessaires mais **ne prouvent pas** le fonctionnement matériel. Les 252 tests rapportés sont un historique, pas un nombre à recopier dans le nouveau compte rendu.

Documents de référence :

- [Installation et utilisation](../../README.md) et [guide LLM Pi 5](../guide-installation-llm-local-pi5.md).
- [Calibration livrée](../../config/runtime_calibration.toml).
- [Tolérances de préparation](../../specs/backlog/05_measurements_tolerance_sheet.md).
- [Modèle de compte rendu à remplir](rapport-test-pi-modele.md).

**Durée indicative :** une demi-journée pour la première qualification, davantage si calibration ou correction nécessaire. Rejouer la campagne complète après modification du contrôle moteur, de la perception, de l'arrêt ou du parsing. Les cas « 3 fois » signifient trois essais indépendants, robot et cible remis dans les mêmes conditions.

## 2. Règles de sécurité et verdicts

### Avant toute commande matérielle

- Prévoir deux personnes pour les essais au sol : opérateur du terminal et observateur avec accès immédiat à la **coupure de l'alimentation moteurs**. Ne pas couper seulement la session SSH.
- Mettre d'abord le robot sur un support stable, roues entièrement dégagées. Au sol : surface plane sans escalier, zone balisée, aucun passant ni animal, arrière dégagé.
- Vérifier batterie, fixation caméra/capteur, GND commun Pi/L298N et câblage hors tension. Vérifier la protection électrique du signal ECHO du HC-SR04 vers le GPIO 3,3 V.
- Les broches sont en **BCM** : moteurs IN1/IN2/IN3/IN4 = 5/6/16/24, ENA/ENB = 12/13 ; TRIG/ECHO = 17/27, sauf adaptation matérielle documentée.
- Un seul programme propriétaire des GPIO/caméra/micro à la fois. Fermer chaque outil avant le suivant. Ne pas lancer un second `smart-car stop` pendant que le runtime détient les GPIO : ce n'est pas un arrêt d'urgence fiable.
- Le recul n'a **aucun capteur arrière**. Les rotations peuvent être bloquées par le capteur frontal. Ne jamais neutraliser une sécurité pour obtenir un test vert.
- Toutes les commandes `voice-runtime --text` ci-dessous peuvent piloter le matériel réel sur Linux. Il n'existe pas ici de mode CLI `--dry-run`.
- Les limites temporelles du runtime ne sont pas un watchdog préemptif. En cas de blocage, ne pas attendre un timeout pour couper les moteurs.

**À tout moment :** mouvement inattendu, arrêt inefficace, obstacle non pris en compte, collision imminente ou recul dangereux → coupure moteurs, arrêt de campagne, **NO-GO**. Garder les preuves et ouvrir une anomalie avant reprise.

### Verdict par cas

- **PASS** : tous les critères observés, preuves attachées, répétitions conformes.
- **FAIL** : résultat différent de l'attendu, même si le programme termine avec un code shell 0.
- **BLOCKED** : prérequis absent ou essai impossible en sécurité ; ne vaut pas PASS.
- **N/A** : uniquement pour une option non activée, avec justification.

Le résultat `[RUNTIME]`, les traces **et l'observation physique** doivent être cohérents. Un `accepted` isolé, un processus vivant ou un code de sortie 0 ne prouvent pas une réussite.

## 3. Préparer l'exécution et les preuves

### P01 — Identifier la livraison et ouvrir le dossier de campagne

Sur le Pi, ouvrir un terminal **Bash**, aller à la racine du projet contenant [pyproject.toml](../../pyproject.toml) et conserver ce terminal pour la campagne :

```bash
bash
cd ~/conf_raspberrypi
set -o pipefail
export PYTHONUNBUFFERED=1
export CAMPAGNE="$PWD/target/logs/test-campaign/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$CAMPAGNE/traces"
touch "$CAMPAGNE/debut"
cp docs/test-campaign/rapport-test-pi-modele.md "$CAMPAGNE/rapport.md"
cp config/runtime_calibration.toml "$CAMPAGNE/calibration-avant.toml"
{
  date -u
  uname -a
  cat /etc/os-release
  uv --version
  uv run python --version
  git rev-parse HEAD
  git status --short
  sha256sum uv.lock config/runtime_calibration.toml
  env | grep '^LLM_'
  free -h
  df -h .
  vcgencmd get_throttled
  vcgencmd measure_temp
} > "$CAMPAGNE/environnement.txt" 2>&1
```

Adapter uniquement le chemin `cd` si le projet est installé ailleurs. Si la livraison est une copie sans `.git`, consigner l'identifiant d'archive et sa provenance à la place du commit. Examiner les erreurs du relevé : absence de `vcgencmd` à signaler ; erreur Python/dépendances à résoudre avant de poursuivre. Une absence de variables `LLM_` signifie utilisation des défauts, pas une erreur LLM.

Ne pas mettre à jour OS, dépendances, modèle ou code au milieu d'une campagne. Si l'installation manque, suivre le README, puis **recommencer P01**. Ne pas exécuter aveuglément des scripts d'installation sur une machine déjà qualifiée.

Définir ce raccourci de capture ; il conserve les erreurs grâce à `pipefail`, mais ne décide pas du verdict métier :

```bash
run_case() {
  local id="$1"
  shift
  printf '\n=== %s | %s ===\n' "$id" "$(date -u)"
  "$@" 2>&1 | tee "$CAMPAGNE/$id.log"
}
```

Reporter dans le compte rendu : matériel, micro choisi, modèle/fichier GGUF, version de llama.cpp, alimentation, diamètre réel de balle, éclairage, sol et opérateurs. Ne pas archiver de secrets ni de voix de tiers.

### P02 — Vérifier le service LLM avant les tests d'intégration

Robot roues levées, moteurs hors tension :

```bash
sudo systemctl start llm.service
systemctl --no-pager status llm.service
curl --fail --show-error --max-time 10 http://127.0.0.1:8080/health
curl --fail --show-error --max-time 10 http://127.0.0.1:8080/v1/models \
  | tee "$CAMPAGNE/modeles.json"
systemctl cat llm.service > "$CAMPAGNE/llm-service.txt"
cat /usr/local/bin/llm-server > "$CAMPAGNE/llm-lanceur.txt"
```

Attendre la fin du chargement si `/health` ne répond pas encore 200, puis relancer les deux requêtes. **PASS :** service actif, API prête, alias attendu `qwen2.5-1.5b` (ou surcharge explicitement enregistrée), bon modèle. Le service doit être prêt avant P03 : le test d'intégration peut sinon tenter de lancer lui-même un autre serveur.

### P03 — Exécuter les tests logiciels sur le Pi

```bash
run_case P03 uv run pytest -q -ra tests/unit tests/integration
```

**PASS :** aucun échec ; relever nombres passés/ignorés et durée. Pour qualifier le LLM local, le test d'intégration ne doit pas être ignoré faute de serveur/modèle.

Ne pas lancer `pytest` sans sélection : les scripts de [tests/hardware/](../../tests/hardware/) se lancent séparément. La suite couvre notamment :

| Garantie logicielle | Preuve automatisée à conserver dans P03 |
|---|---|
| Primitives bornées, validation globale, arrêt final, arrêt après échec | [test_voice_runtime.py](../../tests/unit/test_voice_runtime.py), [test_skills_primitives.py](../../tests/unit/test_skills_primitives.py) |
| Nombres français, unités, gardes, refus sans mouvement, contrats LLM | [test_plan_guards.py](../../tests/unit/test_plan_guards.py), [test_follow_object_wiring.py](../../tests/unit/test_follow_object_wiring.py) |
| Recherche, maintien de distance, perte/réacquisition | [test_skills_behaviors.py](../../tests/unit/test_skills_behaviors.py), [test_follow_object.py](../../tests/unit/test_follow_object.py) |
| Événement d'urgence et interruption | [test_emergency_stop.py](../../tests/unit/test_emergency_stop.py) |
| Distance caméra, calibration, accès capteur | [test_distance_estimator.py](../../tests/unit/test_distance_estimator.py), [test_calibration_helpers.py](../../tests/unit/test_calibration_helpers.py), [test_smart_car_sensor.py](../../tests/unit/test_smart_car_sensor.py) |
| Mission de 300 s simulées et sorties dégradées | [test_scenario_yellow_ball.py](../../tests/unit/test_scenario_yellow_ball.py) |

JSON invalide, HTTP 400, plans artificiellement incohérents, exceptions et bornes extrêmes sont d'abord vérifiés avec ces doubles logiciels. **Ne pas provoquer de longs mouvements physiques pour tester les plafonds de 300 cm ou 600 s.**

## 4. Qualifier les composants, roues levées

### H01 — HC-SR04 réel

Runtime arrêté, moteurs hors tension. Placer une surface plane devant le capteur à 10, 20, 50 puis 100 cm mesurés :

```bash
# Répéter en changeant l'identifiant du journal et la position de la surface.
run_case H01-50cm uv run python tests/hardware/test_hardware_distance.py \
  --trigger-pin 17 --echo-pin 27 --duration 10 --interval 0.1
```

Noter min/max/moyenne et mesures manquantes. Cible d'acceptation de campagne : erreur de moyenne ≤ `max(3 cm, 10 % de la distance réelle)`, pas de série durable de mesures absentes face à la surface. Ce seuil est un **critère de recette**, pas une précision déjà démontrée.

Si une ancienne version du [script matériel](../../tests/hardware/test_hardware_distance.py) échoue avec `unexpected keyword argument 'pull_down'`, récupérer le correctif avant de rejouer H01 : l'entrée ECHO doit être initialisée avec `DigitalInputDevice(args.echo_pin, pull_up=False)`, comme dans le pilote du runtime. `pull_down` n'est pas un argument de cette API ; aucune rétrogradation de gpiozero n'est nécessaire.

### H02 — Caméra et distance visuelle

Si `color-detector --color red --debug` reconnaît la cible mais que la calibration ne la détecte pas, vérifier que le correctif d'ordre des canaux est présent : calibration et perception runtime demandent le format Picamera2 `BGR888`, dont les tableaux sont en ordre RGB, conformément à leur traitement `is_rgb=True`. L'ancien format `RGB888` fournissait des tableaux BGR interprétés à tort comme RGB (rouge et bleu inversés). Ne pas compenser ce défaut par une modification des seuils HSV ; récupérer le correctif et refaire la calibration.

Moteurs hors tension ; balle jaune de diamètre mesuré, éclairage et montage identiques aux essais futurs :

```bash
run_case H02-calibration uv run calibrate-distance --color yellow \
  --ball-diameter-cm 6.5 --known-distance-cm 100 --samples 30
```

Remplacer `6.5` par le diamètre réel. Reporter manuellement la focale affichée **et** ce diamètre dans `[camera]` du TOML, conserver `ultrasonic_fusion = false`, puis :

```bash
cp config/runtime_calibration.toml "$CAMPAGNE/calibration-camera.toml"
run_case H02-controle uv run calibrate-distance --color yellow
```

Ce contrôle est continu : Ctrl+C une fois les mesures relevées. À 50, 100, 150 et 200 cm, noter au moins 10 estimations après stabilisation ; erreur moyenne absolue cible ≤ 15 %. À 100 cm, viser 85–115 cm. Si la balle n'est pas détectée, le mode calibration peut attendre sans fin : interrompre, ne pas valider.

Pour contrôler visuellement couleur et orientation, utiliser `uv run color-detector` avec un écran/session graphique, puis le fermer. En SSH sans affichage, le contrôle textuel précédent et H03 restent utilisables. Refaire le contrôle avec une balle rouge de même diamètre. Vérifier absence de faux positif balle sur le fond seul. Toute modification de résolution/orientation/diamètre invalide la calibration précédente.

### H03 — Prouver que le runtime utilise vraiment le matériel

Une initialisation peut échouer sans arrêter le CLI ; un objet caméra créé ne garantit pas non plus un thread de capture fonctionnel. Avec une balle jaune centrée à 100 cm et une surface visible par le HC-SR04 à moins de 200 cm, moteurs hors tension :

```bash
uv run python - <<'PY' 2>&1 | tee "$CAMPAGNE/H03.log"
import time
from irobot.interfaces.voice_runtime import build_hardware_runtime

hardware = build_hardware_runtime()
try:
    for name in ("robot", "sensor", "perception"):
        if hardware[name] is None:
            raise RuntimeError(f"Matériel absent du runtime : {name}")
    distance = hardware["robot"].read_distance_cm()
    if distance is None or distance <= 0:
        raise RuntimeError("HC-SR04 : pas de mesure exploitable")
    deadline = time.monotonic() + 10
    detection = None
    while time.monotonic() < deadline:
        detection = hardware["perception"].detect(target="yellow")
        if detection is not None and detection.distance_cm is not None:
            break
        time.sleep(0.1)
    if detection is None or detection.distance_cm is None:
        raise RuntimeError("Caméra : pas de balle jaune avec distance en 10 s")
    print("HC-SR04 réel (cm) :", distance)
    print("Détection réelle :", detection)
finally:
    if hardware["perception"] is not None:
        hardware["perception"].close()
    if hardware["robot"] is not None:
        hardware["robot"].stop()
        hardware["robot"].cleanup()
PY
```

**PASS :** aucune exception, détection `yellow_ball`, position `center`, distance cohérente avec H02, capteur cohérent avec H01. Sinon **BLOCKED pour les E2E**, même si une commande texte affiche ensuite `accepted`. Vérifier notamment disponibilité de Picamera2 dans l'environnement `uv`, permissions GPIO et périphériques déjà occupés.

### H04 — Acquisition micro et transcription sans mouvement

Identifier le périphérique :

```bash
arecord -l
export MICRO=wm8960
# Pour un casque Bluetooth configuré, utiliser plutôt : export MICRO=bluetooth
run_case H04 uv run voice-runtime --no-llm --input-device "$MICRO"
```

Moteurs **hors tension**. Dire uniquement « stop », « arrête-toi », « halte », « pause », trois fois chacune, en attendant le résultat entre les phrases. Vérifier les lignes `[VOIX]`, la bonne transcription et le traitement local de l'arrêt. Tester à la distance habituelle d'utilisation et consigner distance/bruit. Ctrl+C pour fermer.

**PASS :** 12/12 arrêts reconnus. Une phrase non transcrite est un échec audio, pas une preuve d'arrêt logiciel. Le test H07 vérifiera l'arrêt avec moteurs audibles et alimentés.

### H05 — Sens moteur et arrêt temporisé

Enlever les objets proches du capteur frontal pour ne pas bloquer ces essais. Alimenter les moteurs, toujours roues levées :

```bash
run_case H05-stop uv run smart-car stop
run_case H05-avant uv run smart-car forward --speed 0.5 --duration 0.5
run_case H05-arriere uv run smart-car backward --speed 0.5 --duration 0.5
run_case H05-gauche uv run smart-car left --speed 0.5 --duration 0.25
run_case H05-droite uv run smart-car right --speed 0.5 --duration 0.25
```

Une commande à la fois, observation avant de poursuivre. **PASS :** deux roues dans le sens attendu, rotations correctes, arrêt réel à chaque fin et pas de redémarrage après sortie. Ne jamais omettre `--duration` : le CLI matériel est continu par défaut.

### H06 — Obstacle prioritaire et arrêt final

Roues levées, surface plane et légère manipulée hors des roues :

1. Surface loin devant (> 50 cm), lancer `run_case H06-r1 uv run voice-runtime --no-llm --text "avance pendant cinq secondes"` ; utiliser `H06-r2` et `H06-r3` aux répétitions pour ne pas écraser le journal précédent.
2. Pendant le mouvement, placer la surface à environ **10–15 cm du HC-SR04** (seuil livré : `< 20 cm`). Chronométrer introduction → arrêt physique.
3. Retirer la surface après arrêt : le robot ne doit pas reprendre la commande. Répéter 3 fois.
4. Relancer avec la surface déjà proche : aucun mouvement soutenu ne doit se produire ; noter toute impulsion.

**PASS :** arrêt physique ≤ 1 s après présentation de l'obstacle, pas de reprise ni retry après l'arrêt de sécurité ; résultat final `aborted`, événement `obstacle_stop`, y compris si l'obstacle est présent avant le démarrage. Toute incohérence entre arrêt physique et statut est à consigner comme FAIL de contrat, pas à masquer.

Sur une livraison antérieure au correctif H06, un obstacle apparu pendant la primitive pouvait arrêter les moteurs tout en laissant un résultat `accepted`, message « Le robot avance. ». Le motif d'interruption est désormais remonté par le contrôleur à la skill puis au runtime, sans relire un obstacle qui pourrait avoir disparu. Rejouer ces cas après récupération du correctif ; ne pas accepter les anciens résultats comme preuve.

La sortie du processus doit aussi être propre : aucun `FATAL: exception not rethrown`. Le pipeline attend désormais la fin de son thread de capture et libère la caméra avant de rendre la main ; une fermeture bloquée reste un échec à investiguer, pas une réussite. Cette correction logicielle doit être confirmée sur le matériel réel.

Le seuil de 1 s est un maximum de recette sur support, **pas** une distance de freinage sûre. Au sol, conserver une marge bien supérieure à la course parcourue pendant ce délai.

### H07 — Arrêt vocal pendant mission, sans LLM puis avec LLM

Roues levées, obstacle frontal retiré, caméra calibrée. Lancer l'écoute continue :

```bash
run_case H07-local uv run voice-runtime --no-llm --input-device "$MICRO"
```

1. Dire « suis la balle jaune à un mètre pendant trente secondes ». Déplacer la balle pour provoquer une rotation ou une correction de distance.
2. Dès qu'une mission est active, dire « avance de vingt centimètres » : message « Mission en cours : phrase ignorée », aucune seconde mission.
3. Pendant une impulsion visible, dire « stop ». Mesurer séparément fin de la parole → arrêt physique et ligne `[VOIX] stop` → arrêt physique (vidéo horodatée recommandée).
4. Vérifier `aborted`, `emergency_stop`, pas de retry ni reprise. Attendre la fin du worker, puis redonner une commande courte pour vérifier la réutilisation après effacement de l'urgence.
5. Répéter l'arrêt 3 fois ; fermer avec Ctrl+C.
6. Refaire avec `run_case H07-llm uv run voice-runtime --input-device "$MICRO"` ; attendre le préchauffage avant les missions, 3 arrêts.
7. Pendant une nouvelle mission, faire Ctrl+C : arrêt physique ≤ 1 s et sortie sans reprise.

**PASS :** tous les arrêts réussissent ; objectif de recette fin de parole → arrêt ≤ 2 s et transcription visible → arrêt ≤ 1 s. Noter les valeurs réelles, pas seulement une impression. Ces seuils ne sont pas des garanties de l'audit. Un stop prononcé pendant l'inférence initiale ne qualifie pas l'interruption d'une skill : mesurer aussi l'arrêt pendant le mouvement.

**GATE A — Autorisation des essais au sol :** P01–P03 et H01–H07 PASS, calibration sauvegardée, coupure moteurs accessible. Sinon NO-GO. La voix et Ctrl+C restent des arrêts logiciels, pas une sécurité matérielle certifiée.

## 5. Calibrer puis qualifier les mouvements au sol

### M01 — Distances et angles

Zone dégagée, observateur prêt à couper, repères au sol et mètre/rapporteur. Vitesse runtime livrée : 0,5. Commencer par 10 cm ; ne passer aux distances suivantes qu'après arrêt conforme :

```bash
run_case M01-10cm-r1 uv run voice-runtime --no-llm --text "avance de dix centimètres"
run_case M01-20cm-r1 uv run voice-runtime --no-llm --text "avance de vingt centimètres"
run_case M01-50cm-r1 uv run voice-runtime --no-llm --text "avance de cinquante centimètres"
run_case M01-droite45-r1 uv run voice-runtime --no-llm --text "tourne à droite de quarante cinq degrés"
run_case M01-droite90-r1 uv run voice-runtime --no-llm --text "tourne à droite de quatre vingt dix degrés"
run_case M01-gauche90-r1 uv run voice-runtime --no-llm --text "tourne à gauche de quatre vingt dix degrés"
run_case M01-recul10-r1 uv run voice-runtime --no-llm --text "recule de dix centimètres"
```

Faire 3 essais par commande avec identifiants `r1/r2/r3`. Mesurer distance, angle, dérive latérale et arrêt final. Cibles de recette : erreur distance ≤ 20 %, angle ≤ 15° pour chaque essai ; noter aussi moyennes et dispersion.

Si nécessaire, ajuster `[runtime] cm_per_second` et `deg_per_second` dans le TOML. Les valeurs initiales sont **25 cm/s et 360°/s**, pas une calibration physique acquise. Pour une commande fondée sur distance/angle : nouvelle conversion ≈ ancienne conversion × mesure / consigne. Refaire les séries après ajustement, à batterie et sol comparables ; ne pas corriger le mauvais sens moteur par la calibration.

Premier relevé M01 : 10/20/50 cm demandés donnent 16/44/110 cm réels avec 25 cm/s configurés. Les deux grandes distances conduisent à une calibration provisoire de **55 cm/s** (`25 × 44 / 20 = 25 × 110 / 50`). Cette valeur est reportée dans le TOML, mais reste à confirmer par trois essais par distance ; le point à 10 cm révèle une réponse courte non proportionnelle. Redémarrer le runtime après changement de configuration.

Avec les anciens réglages (25 cm/s, 360°/s), le recul demandé de 10 cm donne 10 cm et les rotations demandées de 45°/90° donnent environ 20°/45°, des deux côtés. Le TOML retient provisoirement **180°/s** pour les rotations et **25 cm/s** dans `backward_cm_per_second` pour préserver le recul indépendamment de l'avance à 55 cm/s. Cette clé s'applique aux primitives de recul et aux impulsions de régulation du suivi ; absente, elle conserve le comportement historique utilisant `cm_per_second`. Une durée explicite reste inchangée. Récupérer aussi le code qui lit cette nouvelle clé, pas seulement le TOML. Refaire trois mesures à gauche/droite pour 45° et 90°, ainsi que le recul, avant validation ; un recul correct à 10 cm ne qualifie pas les autres distances.

### M02 — Commandes sans paramètre et séquence

```bash
run_case M02-avance uv run voice-runtime --no-llm --text "avance"
run_case M02-recule uv run voice-runtime --no-llm --text "recule"
run_case M02-tourne uv run voice-runtime --no-llm --text "tourne à droite"
run_case M02-plan uv run voice-runtime --no-llm \
  --text "avance de vingt centimètres puis tourne à droite de quatre vingt dix degrés"
```

**PASS :** avance/recul bornés à 1 s de mouvement, rotation par défaut 90°, ordre correct des étapes de la séquence, arrêt final effectif. Examiner `plan_validated` ; ne pas mesurer les 1 s depuis le lancement du processus (initialisation matérielle exclue).

## 6. Qualifier le LLM et ses modes dégradés

### L01 — Démarrage à froid, serveur chaud et qualité des plans

Roues levées pour isoler les risques d'interprétation, puis reprendre au sol seulement pour les cas déjà qualifiés. Aucun runtime actif :

```bash
sudo systemctl restart llm.service
# Attendre /health = 200 avant la première commande.
curl --fail --show-error --max-time 10 http://127.0.0.1:8080/health
run_case L01-froid uv run voice-runtime --text "avance de vingt centimètres"
run_case L01-chaud-r1 uv run voice-runtime --text "avance de vingt centimètres"
run_case L01-angle uv run voice-runtime --text "tourne à droite de quatre vingt dix degrés"
run_case L01-metres uv run voice-runtime --text "avance de un mètre"
```

Répéter le cas chaud 5 fois (`r1` à `r5`). Pour chaque essai, relever `source`, `normalized_text`, plan validé, `warmup_status`, latence LLM, nombre de requêtes, format, tokens et erreur éventuelle. Distinguer durée totale du processus, attente de préchauffage, inférence et exécution. Le CLI recrée un préchauffage à chaque lancement ; « chaud » décrit ici le serveur/modèle déjà chargé, pas une session CLI persistante.

**PASS fonctionnel :** plans conformes à la phrase, pas de nombre ajouté/perdu ; au moins un vrai `source=llm_plan` pour chaque commande retenue et 5/5 cas chauds simples sans repli. Un succès via parseur local ne qualifie pas le LLM. Rapporter taux de repli, latences médiane/max et débit si les timings serveur le permettent. Pas d'objectif arbitraire de 800 ms ; timeout de lecture livré 10 s, connexion 1 s, attente de préchauffage 60 s. Une modification de ces réglages impose une nouvelle série identifiée.

### L02 — Refus hors périmètre sans mouvement

Roues levées, exécuter séparément :

```bash
run_case L02-meteo uv run voice-runtime --text "quelle est la météo demain"
run_case L02-poeme uv run voice-runtime --text "raconte un poème"
run_case L02-cafe uv run voice-runtime --text "prépare un café"
```

**PASS :** 3/3 rejets, `steps` exécutées vide, aucun mouvement ; `plan_unsupported` si source `llm_unsupported` ou `llm_ungrounded`. Aucun repli local pour ces deux sources. Si une panne technique entraîne un repli, rétablir le service et rejouer : ce n'est pas une preuve de fonctionnement des gardes sur une réponse LLM.

### L03 — Serveur indisponible et stop indépendant du LLM

Arrêter les autres runtimes, roues levées. Noter l'état initial du service ; s'il était actif, le restaurer même si l'essai échoue :

```bash
sudo systemctl stop llm.service
# Échec de connexion attendu ; si une API répond encore, identifier le serveur avant de continuer.
curl --fail --show-error --max-time 2 http://127.0.0.1:8080/health
run_case L03-repli uv run voice-runtime --text "avance de vingt centimètres"
run_case L03-stop uv run voice-runtime --text "stop"
sudo systemctl start llm.service
# Attendre de nouveau /health = 200 et confirmer /v1/models.
```

**PASS :** repli annoncé avec motif technique, `source=local_parser_fast_fallback`, erreur tracée, distance 20 cm préservée, arrêt final. Pour « stop » : `source=local_stop`, aucun appel d'interprétation LLM ni attente de préchauffage ; le CLI peut cependant avoir démarré sa requête de préchauffage en arrière-plan. Ne pas interpréter ce dernier point comme un appel LLM pour comprendre « stop ».

Le refus de connexion ne reproduit pas un timeout de lecture : vérifier ce dernier et l'absence de second essai après timeout dans P03. Ne pas bloquer un serveur partagé ni modifier son réseau pour fabriquer une panne.

## 7. Cas de référence, progressivement au sol

Reprendre la configuration calibrée, fusion ultrason désactivée. Commencer chaque cas avec cible et robot sur repères, balle jaune seule, caméra/sol/éclairage constants. Ne pas se placer entre le robot et la balle. Utiliser une cible sur support déplaçable sans approcher les mains des roues.

### E01 — Recherche et approche seule

```bash
run_case E01-r1 uv run voice-runtime --no-llm \
  --text "cherche la balle jaune puis approche-toi à un mètre"
```

Présenter la balle initialement décalée, à environ 150 cm, puis recommencer de l'autre côté. Faire aussi un essai où elle n'est présentée qu'après 4 s de recherche. **PASS :** recherche bornée, correction du bon côté, alignement avant avance, ralentissement à l'approche, arrêt autour de la consigne (distance réelle cible 85–115 cm).

L'approche dispose d'un budget de poursuite court distinct de la recherche : si la cible est trop lointaine pour être atteinte, documenter le résultat au lieu d'allonger les délais sans justification. L'audit signale qu'un premier `detect_object` en échec peut provoquer un retry : consigner tentatives et délai avant recherche, ne pas les cacher.

### E02 — Suivi court : 30 s

```bash
run_case E02-r1 uv run voice-runtime --no-llm \
  --text "suis la balle jaune à un mètre pendant trente secondes"
```

Au départ, balle centrée à 100 cm. Pendant le suivi : l'éloigner vers 150 cm, la décaler latéralement, la rapprocher vers 70 cm en gardant l'arrière du robot libre, puis l'immobiliser à 100 cm. Répéter 3 fois.

**PASS :** avance, alignement et recul corrects ; arrêt dans la zone morte, absence d'oscillation dangereuse ; fin vers 30 s **depuis le début de la skill**, arrêt moteur final. Viser 30 ± 2 s ; relever durée de skill dans le résultat et chronométrage physique, pas seulement durée totale du CLI.

### E03 — Perte de cible et réacquisition

Relancer E02 avec un identifiant E03 :

1. Masquer brièvement la balle (environ 1 s) : arrêt de translation pendant la perte, puis reprise après détection.
2. La masquer plus de 3 s puis la représenter avant épuisement du budget de recherche : balayage et reprise, pas de translation aveugle.
3. Essai séparé : `run_case E03-absente uv run voice-runtime --no-llm --text "suis la balle jaune à un mètre pendant soixante secondes"` sans aucune balle.

**PASS :** jamais d'avance/recul sans cible exploitable ; perte prolongée → arrêt final, résultat non réussi (`incomplete`/`aborted` selon budget réellement atteint), pas de mouvement sans fin. Relever chaque tentative : 25 s est le budget de recherche par tentative, pas nécessairement la durée totale du processus avec retries et contrôles après exécution. Couper si le comportement devient dangereux.

### E04 — Mission vocale complète de cinq minutes

Condition : E01–E03 et L01 PASS. Lancer **l'écoute continue**, pas `--text` ni `--once`, afin de conserver l'arrêt vocal pendant la mission :

```bash
run_case E04-r1 uv run voice-runtime --input-device "$MICRO"
```

1. Attendre le préchauffage. Dire : **« Cherche la balle jaune, approche-toi à un mètre puis suis-la pendant cinq minutes. »**
2. Vérifier `[VOIX]` puis le plan : recherche/approche `yellow`, consigne 100 cm ; `follow_object`, même cible, consigne 100 cm, `duration_s=300`. Examiner ensuite les éventuelles expansions déterministes dans `plan_validated`.
3. Commencer balle visible décalée à environ 150 cm. Vérifier approche puis début du suivi. Chronométrer séparément ces phases.
4. Pendant les 300 s de suivi, déplacer lentement la balle dans la zone autorisée ; inclure des périodes fixes et de petites pertes visuelles déjà qualifiées en E03.
5. Après chaque déplacement, laisser stabiliser 3 s. Relever au moins 10 mesures physiques réparties sur les cinq minutes, caméra → balle, sans pénétrer la trajectoire ; vidéo et repères au sol recommandés.
6. Attendre la fin naturelle sans dire stop ; observer l'immobilité au moins 10 s après la fin. Fermer ensuite le runtime avec Ctrl+C.

**PASS :** transcription et paramètres corrects ; vrai plan LLM, résultat final `accepted`, `mission.phase=success`, pas de repli caché ; suivi réel **300 ± 5 s** depuis le début de `follow_object`, non interrompu à 12 ou 45 s ; arrêt final effectif. Au moins 9/10 mesures stabilisées à **100 ± 15 cm**, sans excursion dangereuse ni contact ; consigner toutes les mesures, y compris les ratées. Ce seuil est un objectif de recette, pas une précision matérielle acquise.

Le budget d'étape livré pour 300 s vaut `max(6, 300 + 25 + 10) = 335 s`, pas une durée à attendre pour déclarer le suivi réussi. Les 300 s incluent les recherches/pertes **dans la skill de suivi**, mais pas l'approche précédente ni l'inférence.

Faire **3 missions complètes**. Aucun essai interrompu pour sécurité ou terminé sur repli local ne compte comme réussite E04.

### E05 — Interruptions de la mission complète

Reprendre E04 en écoute continue avec une nouvelle mission pour chaque variante :

| Variante | Action | Résultat requis |
|---|---|---|
| E05-stop | Vers 60 s de suivi, dire « stop » | Arrêt dans les seuils H07, `aborted`, `emergency_stop`, aucun retry ni étape ultérieure |
| E05-obstacle | Vers 100 s, présenter une surface plane à 10–15 cm du HC-SR04, hors trajectoire des roues | Arrêt dans le seuil H06, `aborted`, `obstacle_stop`, aucune reprise après retrait |
| E05-clavier | Pendant un mouvement, Ctrl+C | Arrêt physique ≤ 1 s, pas de reprise, fermeture du runtime |

Qualifier d'abord le geste d'introduction d'obstacle roues levées en H06 ; au sol, ne pas utiliser une personne comme obstacle. Après chaque interruption, attendre la fin effective de la mission avant un nouvel ordre. L'absence de `mission_result` après Ctrl+C ne suffit pas à conclure à une panne : conserver console et vidéo de fermeture.

**GATE B — Bout en bout qualifié :** E04 réussi 3/3 et E05 entièrement PASS, en plus de GATE A, M01–M02 et L01–L03.

## 8. Endurance, options et limites connues

### Q01 — État après les trois missions et redémarrage

Pendant E04, depuis un second terminal sans ouvrir de périphérique matériel :

```bash
top -b -n 1
free -h
vcgencmd measure_temp
vcgencmd get_throttled
```

Relever au repos, pendant la première mission, pendant la troisième et après. Conserver les sorties dans le dossier de campagne. Comparer RAM/swap, CPU, température, états de sous-tension/throttling et latences ; ne pas déduire une fuite d'une seule mesure. **PASS :** pas de crash/OOM, de sous-tension active ni de throttling actif, pas de dégradation inexpliquée empêchant les critères d'arrêt/suivi. Les bits historiques de `get_throttled` sont à distinguer de l'état actif.

Puis, moteurs hors tension et runtimes fermés : redémarrer le Pi, vérifier service/API P02, refaire H03, un arrêt vocal H07 et une mission E04. Ouvrir un nouveau dossier P01 après redémarrage et le relier au rapport principal ; les fonctions/variables Bash ne sont pas persistantes.

### Q02 — Fusion ultrason optionnelle

**N/A si la configuration de livraison garde `ultrasonic_fusion=false`.** Si cette option est réellement destinée à être livrée : sauvegarder la configuration de référence, activer la fusion dans une campagne distincte, répéter H01–H03, H06–H07 et E01–E05. Vérifier cible centrée et cohérence visuel/ultrason à ±25 % ; une mesure incohérente ne doit pas tirer la distance vers l'obstacle. Conserver les mesures comparées. Ne pas mélanger les résultats fusion activée/désactivée.

### Q03 — Réserves de l'audit à rendre visibles

| Limite connue | Traitement dans la campagne |
|---|---|
| Capteur optionnel à l'initialisation (`require_obstacle_sensor=False`) | H03 et H06 obligatoires ; pas d'essai au sol avec capteur absent. Un essai d'absence éventuel se prépare hors tension et reste roues levées, sans valeur de qualification sûre. |
| Rotation bloquée par obstacle frontal | Vérifier roues levées si nécessaire et consigner ; ne pas promettre un contournement qualifié. |
| Timeouts contrôlés après exécution | Couverture P03 + arrêt physique H06/H07 ; ne pas prétendre avoir testé un watchdog matériel. |
| Décodage tolérant d'étapes malformées | P03 ; rejet atomique à la validation, pas garantie de rejet de toute réponse brute. |
| `step_result` brut parfois `accepted` avant correction du statut final | Lire console, `results` des skills et `mission_result`, pas seulement cet événement intermédiaire. |
| Retour au départ sans odométrie/mémoire intercommandes | Hors qualification de localisation ; ne pas en faire un critère du cas balle jaune. |
| Voie legacy, cercle, contournement et scripts historiques | Non qualifiés par cette campagne ; campagne séparée si destinés à la livraison. |

Une réserve connue n'autorise jamais un défaut d'arrêt physique. Toute dérogation fonctionnelle doit être explicitement acceptée et le périmètre qualifié réduit dans le rapport.

## 9. Fermer la campagne et décider

Tous les runtimes arrêtés, roues sécurisées et moteurs coupés :

```bash
cp config/runtime_calibration.toml "$CAMPAGNE/calibration-apres.toml"
find target/logs -maxdepth 1 -type f -name 'runtime_trace_*.jsonl' \
  -newer "$CAMPAGNE/debut" -exec cp {} "$CAMPAGNE/traces/" \;
journalctl -u llm.service --since "$(date -r "$CAMPAGNE/debut" --iso-8601=seconds)" \
  --no-pager > "$CAMPAGNE/llm-journal.txt"
```

La commande `date -r ... --iso-8601=seconds` ci-dessus est prévue pour GNU date sur le Pi. Ne pas effacer les traces originales. Associer **chaque essai** à son `trace_path` indiqué en console ; les refus peuvent s'arrêter à `plan_unsupported`/`plan_validated` sans `mission_result`.

Dans chaque trace JSONL réussie, examiner `input`, `plan_raw`, `plan_validated`, `step_result`, `mission_result`. Pour un arrêt de sécurité, chercher aussi `emergency_stop` ou `obstacle_stop`. L'arrêt vocal pendant une mission peut être visible dans la console sans nouvelle trace d'entrée dédiée : conserver la console complète et les mesures vidéo.

Compléter le rapport, lier photos/vidéos/journaux, enregistrer anomalies et configuration exacte. Conserver les réglages réellement qualifiés dans la livraison ; tout changement ultérieur crée une nouvelle référence.

**Décision finale :**

- **GO** : tous les cas obligatoires PASS, y compris la mission après redémarrage ; options non livrées en N/A justifié ; aucune anomalie de sécurité ouverte.
- **NO-GO** : un FAIL/BLOCKED obligatoire, une preuve manquante, un arrêt non maîtrisé, ou un succès uniquement simulé.
- Après correction : nouvelle livraison identifiée, reprise au minimum du cas échoué et de tous ses prérequis impactés ; campagne complète pour un changement touchant la chaîne de sécurité ou de suivi.
