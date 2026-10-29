# Audit d'Architecture, Sécurité & Performance — Synthèse V6

**Projet :** Runtime robotique local Python (`irobot`)  
**Plateforme cible :** Raspberry Pi 5 — Smart Car 2WD, caméra OV5647, HC-SR04  
**Date de synthèse :** 29 octobre 2026  
**Périmètre :** audit et refactoring menés avec Claude-Code, formalisés en étapes d'implémentation Copilot  
**État :** étapes 1 à 10 finalisées côté logiciel sur Mac ; validation physique sur Pi restante.

### Sources et méthode

- [REFERENCE_IROBOT.md](../../audit-by-claude/v6/REFERENCE_IROBOT.md) : architecture de départ, contrats et risques R1 à R12 ; document partiellement actualisé après les travaux LLM.
- [PROMPTS_COPILOT.md](../../audit-by-claude/v6/PROMPTS_COPILOT.md) : découpage du refactoring, critères de test, mesures LLM et protocole d'essai matériel.
- [PROJECT_CONTEXT.md](../../../PROJECT_CONTEXT.md) : confirmation des réalisations, correctifs des étapes 8b/8c et bilan de validation de l'étape 10.

Cette synthèse distingue les constats initiaux, les changements documentés comme réalisés et les validations restantes. Les prompts décrivent des demandes, pas à eux seuls des preuves d'exécution. Les résultats de tests ci-dessous sont ceux consignés dans le contexte projet ; ils n'ont pas été réexécutés pour cette rédaction.

---

## 1. Synthèse Majeure & Bilan de l'Architecture

Le chantier a transformé un runtime de commandes courtes en une chaîne capable de rechercher un objet, de l'approcher à une distance cible puis de le suivre pendant une durée définie, tout en conservant une écoute d'arrêt d'urgence.

**Cas d'usage de référence :**

> « Cherche la balle jaune, approche-toi à 1 m puis suis-la pendant 5 min. »

Le contrat logiciel correspondant est un plan `search_and_approach_object` puis `follow_object`, avec cible `yellow`, distance de consigne `stand_off_cm=100` et durée de suivi `duration_s=300`.

### Points forts consolidés

- **Commande déterministe :** le LLM ne pilote jamais les GPIO. Il propose des intents que le runtime normalise, contrôle, borne et traduit en skills.
- **Arrêt en sortie de mission :** appel à `robot.stop()` dans un `finally`, y compris après échec ou exception. Cela garantit la tentative d'arrêt logiciel, pas son efficacité matérielle si cet appel échoue.
- **Exécution cohérente :** rejet complet d'un plan contenant une étape invalide à la validation ; arrêt après une étape en échec ou interrompue.
- **Perception exploitable :** la détection couleur fournit désormais un diamètre apparent et une estimation de distance, au lieu d'une distance systématiquement absente.
- **Suivi en boucle fermée :** recherche, alignement, approche, maintien de distance et réacquisition utilisent la perception courante.
- **Testabilité :** horloges injectables, `FakeRobot` et monde simulé permettent de couvrir 300 secondes de suivi sans attente réelle ni matériel.

### Architecture après refactoring

```text
Micro -> Vosk -> transcription
                  |
                  +-- arrêt pur -> arrêt local, sans LLM
                  |
                  v
Prétraitement déterministe -> LLM local -> plan JSON
                                  |
                      erreur technique -> parseur local
                                  |
                                  v
Gardes lexicales -> normalisation / expansion -> validation / bornage
                                  |
                                  v
VoiceRuntime -> LanguageController -> Planner / Executor -> Skills
                                  |
                                  v
                         RobotController -> GPIO / L298N
                                  ^
Caméra -> détection couleur -> distance lissée
HC-SR04 -> obstacle prioritaire / fusion de distance optionnelle
```

En écoute continue, la mission s'exécute dans un thread de travail ; le thread d'écoute reste disponible pour demander l'arrêt. Le chemin synchrone est conservé pour les tests et le mode `--once`.

**Rectification du V5 :** la pile documentée utilise Python, Vosk, OpenCV, `gpiozero` et le L298N. ROS2, Whisper, PCA9685, encodeurs en quadrature et balises ArUco ne sont pas établis par les sources. Les déplacements restent calibrés en boucle ouverte, sans odométrie.

---

## 2. Diagnostic Initial & Refactoring Réalisé

### A. Sécurité d'exécution et budgets temporels — étapes 1 et 2

L'audit initial relevait des primitives potentiellement continues, l'absence d'arrêt systématique en fin de plan et la poursuite d'une mission après une étape en échec.

Les corrections documentées apportent :

- des valeurs par défaut bornées : **1 s** pour avancer/reculer, **90°** pour tourner si aucun paramètre de mouvement n'est fourni ;
- une normalisation partagée des unités de distance dans le runtime et les primitives ;
- un arrêt final et l'interruption des étapes suivantes en cas d'échec ;
- un rejet global à la validation, avec conservation de `validation_errors`, plutôt qu'une exécution partielle ;
- des plafonds propres au suivi long, distincts des primitives courtes.

Le timeout effectif d'une étape portant `duration_s` devient :

```text
max(step_timeout_seconds, duration_s + search_timeout_s + timeout_margin_seconds)
```

Le budget de mission est le maximum entre son réglage nominal et la somme des budgets des étapes. Avec les valeurs livrées, un suivi de 300 s dispose ainsi d'un budget d'étape de **335 s**. Ces budgets ne constituent toutefois pas un watchdog préemptif : le contrôle du dépassement reste effectué après l'appel d'exécution.

### B. Distance visuelle et accès au capteur — étape 3

- Remontée des métriques géométriques des candidats sans casser les verdicts texte historiques.
- Diamètre apparent calculé à partir de l'aire, invariant à la rotation de l'image.
- Estimation sténopé : `distance_cm = focal_px * ball_diameter_cm / diameter_px`.
- Lissage exponentiel, coefficient **0,4**, et commande `calibrate-distance` pour déterminer la focale.
- Fusion ultrason optionnelle : cible centrée et mesure cohérente à **±25 %** de l'estimation visuelle ; désactivée par défaut.
- Accès HC-SR04 sérialisé par verrou et cache de **50 ms** ; fusion dans `detect()`, jamais depuis le thread caméra.
- Correction d'un appel de détection avec un paramètre inexistant qui empêchait la remontée des objets.

La distance devient disponible pour la commande, mais sa précision physique dépend encore du diamètre réel de la balle, de la calibration et des conditions d'image.

### C. Recherche, approche et suivi — étapes 4 à 6

`FollowTargetSkill` sépare désormais **SEARCH** et **TRACK**. Le budget de recherche est distinct de la courte tolérance de perte de cible. Le balayage privilégie la dernière direction connue ; l'approche réduit les impulsions à proximité de la consigne.

Le nouveau `FollowObjectSkill` :

- aligne le robot avant de corriger la distance ;
- avance si la cible est trop éloignée, recule par impulsions courtes si elle est trop proche ;
- s'arrête dans une zone morte autour de la consigne, par défaut **100 ±15 cm** ;
- arrête le mouvement lors d'une perte de cible, puis recherche et reprend le suivi si elle réapparaît ;
- termine à la durée demandée avec arrêt en sortie.

Le refactoring extrait les opérations communes dans `TargetTrackingMixin` : détection, balayage, impulsions, arrêt et contrôles de sécurité. L'intent `follow_object` est câblé dans le registre, le planner, le validateur, le runtime et le parseur local. Les cibles rouge/jaune, distances, minutes et références à une cible précédente sont normalisées.

### D. Arrêt vocal pendant une mission — étape 7 et consolidation étape 9

`RobotController` expose un événement d'urgence partageable entre threads. En cours de mission, une phrase d'arrêt déclenche immédiatement la demande d'arrêt ; les autres commandes sont ignorées avec un message.

Les skills conservent leur convention de résultat `success` accompagnée de drapeaux de sécurité. Le runtime convertit une urgence ou un obstacle signalé en mission **`aborted`**, sans retry ni étape suivante. La fermeture demande également l'arrêt et attend le worker avec une limite de 2 s.

---

## 3. Diagnostic des Performances LLM & Optimisations Appliquées

### A. Modèle et contrat de sortie — étape 8

La configuration cible est passée à **Qwen2.5-1.5B-Instruct, GGUF Q4_K_M**, servi localement par `llama-server`, alias `qwen2.5-1.5b`, contexte **2048**, service `llm.service`.

Le runtime conserve un appel HTTP **synchrone, non streamé**. Le travail réalisé porte sur :

- un prompt court et statique, une température de **0**, un budget de **120 tokens** pour le plan et **96** pour l'intent unique ;
- le prétraitement Python des nombres français, mètres et minutes avant l'inférence ;
- la conservation du texte d'origine et la trace du texte normalisé ;
- le cache de prompt demandé au serveur et le préchauffage au démarrage ;
- le repli local immédiat en cas d'erreur technique, sans second essai LLM après timeout.

### B. Gardes déterministes et JSON contraint — étape 8b

L'évaluation a montré qu'un JSON valide ne garantit pas une commande pertinente : les deux prompts comparés ne refusaient **aucune des 9 consignes hors périmètre** du jeu considéré.

Les protections ajoutées ne reposent donc pas uniquement sur le modèle :

- arrêt pur reconnu **sans appel LLM** ;
- `grounding_check` confrontant intents et nombres à la phrase normalisée ;
- rejet sans mouvement ni repli d'un plan non justifié ou d'un `{"steps":[]}` explicite ;
- suppression des arrêts parasites et paramètres non gérés ;
- sortie `json_schema` stricte, puis replis de compatibilité sur HTTP 400 : `json_object` avec schéma, `json_object`, sans format ; mémorisation du premier format accepté.

**Nuance de contrat :** le rejet atomique concerne les étapes arrivant à la validation. Le décodage LLM reste tolérant : une étape malformée peut être ignorée seule et signalée par `skipped_steps`. Ce comportement n'équivaut pas à une validation atomique de la réponse brute entière.

### C. Démarrage à froid et observabilité — étape 8c

Le timeout de lecture a évolué de **4 à 8 puis 10 s**, après observation de plans dépassant 8 s. Le timeout de connexion reste **1 s**. Ces valeurs sont configurables.

Les traces exposent désormais la latence réelle, le format utilisé, le nombre de requêtes HTTP, les tokens, les timings serveur, le type d'erreur et l'état du préchauffage. `LLM_RESPONSE_FORMAT` permet de comparer `schema`, `json_object` et `none`.

En mode `--once`/`--text`, la requête attend la fin du préchauffage, au plus **60 s** par défaut, puis continue même si celui-ci échoue ou expire. En écoute continue, le préchauffage reste non bloquant. Le motif du repli local est annoncé en console.

---

## 4. Matrice d'Évaluation & Bilan de Validation

### Mesures LLM rapportées

| Indicateur | Résultat consigné | Portée / réserve |
| :--- | :--- | :--- |
| Prompt v1 + schéma | **69/81 corrects**, soit 85,2 % ; médiane 1,9 s, maximum 5,5 s | Évaluation rapportée en 8b ; aucune boucle de génération |
| Prompt v2 + schéma | **57/81 corrects**, soit 70,4 % | Régressions multi-étapes ; v2 abandonné |
| Refus hors périmètre par le modèle seul | **0/9** pour les deux prompts | Justifie les gardes déterministes ; ne mesure pas leur efficacité après ajout |
| Plan du cas d'usage, serveur chaud | **4,3 à 7,7 s** | Mesures Mac rapportées en 8c, pas benchmark Pi |
| Premier appel après démarrage | **35,6 s** | Observation Mac motivant l'attente de préchauffage |
| Débit observé | **Environ 11 tokens/s** | Observation Mac ; débit Pi à mesurer |
| RAM, CPU, taux de timeout sur Pi | **Non établis** | Les objectifs chiffrés du V5 ne sont pas des résultats acquis |

### Paramètres livrés

| Paramètre | Valeur | Interprétation |
| :--- | :--- | :--- |
| Primitives : distance / angle / durée maximum | 300 cm / 360° / 12 s | Distinct du plafond de suivi |
| Distance de consigne objet | 30–300 cm | Bornage runtime |
| Durée de suivi | 1–600 s | Cas d'usage : 300 s |
| Recherche | Défaut 25 s ; paramètre borné à 1–120 s | Budget distinct de la perte courte de cible |
| Marge de timeout | 10 s | Ajoutée au budget des étapes avec `duration_s` |
| Diamètre balle / focale initiale | 6,5 cm / 600 px | Focale à calibrer |
| Conversion de déplacement | 25 cm/s ; 360°/s | Valeurs actuelles du TOML, à calibrer ; ne pas reprendre les anciens 65 cm/s comme valeur livrée |

### Validation logicielle consignée — étapes 9 et 10

- **252 tests réussis** dans la suite portable : `uv run pytest -q tests/unit tests/integration`.
- Syntaxe du script de scénarios standards et contrôle `git diff --check` annoncés conformes à l'étape 10.
- Scénario simulé : balle absente 4 s, détection à droite à 220 cm, approche à environ 1 m, suivi sur 300 s simulées.
- Couverture des sorties dégradées : cible jamais trouvée, arrêt d'urgence à 60 s, obstacle à 100 s ; contrôle de l'arrêt final et des traces.
- Ajout du scénario « Yellow ball » au script de scénarios standards Mac ; documentation README et specs alignée.

**Limite :** cette simulation utilise le parseur local, une perception et une horloge simulées. Elle valide l'intégration logicielle, pas la reconnaissance Vosk, la qualité du LLM sur Pi ni la précision mécanique du maintien de distance. La collecte globale `uv run pytest -q` échoue sur Mac dans les tests matériels faute de `gpiozero`, avec un `SystemExit` de test hardware ; ne pas présenter cette commande comme entièrement verte.

---

## 5. Conclusion & Prochaines Étapes

### Bilan des risques de l'audit initial

| Risque initial | État après le chantier |
| :--- | :--- |
| R1 — Primitives continues sans paramètres | Corrigé sur le chemin runtime par défauts bornés |
| R2 — Absence d'arrêt final | Appel d'arrêt ajouté en `finally` ; efficacité matérielle à vérifier |
| R3 — Rotations bloquées par obstacle frontal | Non déclaré corrigé ; évitement/contournement à revoir |
| R4 — Capteur optionnel à l'initialisation | Risque restant : construction avec `require_obstacle_sensor=False` |
| R5 — Poursuite après échec / plan partiel | Interruption après échec et validation globale ; réserve sur le décodage tolérant |
| R6 — Timeouts incohérents | Budgets adaptés au suivi long ; absence de préemption générale restante |
| R7 — Distances/angles perdus en repli local | Corrigé ; nombres français et unités pris en charge |
| R8 — Distance caméra absente | Estimation ajoutée ; précision et calibration matérielles non validées |
| R9 — Voie legacy incohérente | Non déclarée corrigée ; chemin principal à privilégier |
| R10 — Retour au départ limité au plan courant | Limite inchangée ; aucune odométrie ni mémoire intercommandes |
| R11 — `MoveCircleSkill` | Hors périmètre du chantier, non déclaré corrigé |
| R12 — Dérives documentaires | README/specs actualisés ; références historiques et scripts à harmoniser |

### Priorités restantes

1. **Valider physiquement sur Pi**, d'abord roues levées : sens moteur, arrêt logiciel, arrêt vocal et comportement capteur. Le recul de régulation n'a pas de capteur arrière.
2. **Calibrer la distance et les mouvements** : focale avec `calibrate-distance --known-distance-cm 100`, contrôle à plusieurs distances, puis ajustement des conversions distance/angle.
3. **Tester progressivement le cas d'usage** : approche seule, suivi court de 30 s, puis 5 min en zone dégagée. Ne pas considérer les 100 ±15 cm comme une précision matérielle déjà démontrée.
4. **Mesurer sur Pi** la latence à froid/à chaud, le débit, les replis et les faux rejets des gardes lexicales ; aucune garantie de réponse sous 800 ms n'est établie.
5. **Lever les limites connues** : politique d'absence du capteur, rotations face à un obstacle, timeouts non préemptifs et sémantique du parsing tolérant. Le contexte signale aussi un échec initial de `detect_object` avant recherche pouvant provoquer une seconde tentative, et un `step_result` brut parfois `accepted` malgré l'échec d'une skill.
6. **Terminer le nettoyage de l'étape 11**, non confirmé comme achevé : scripts Mac/Pi, anciennes références de modèle/contexte/service, cohérence du prétraitement avec le script d'évaluation et documentation historique.

**Conclusion :** le refactoring apporte une chaîne logicielle cohérente et testée sans matériel pour le scénario « recherche → approche → suivi », avec une séparation renforcée entre proposition LLM et décision runtime. Il ne constitue ni une certification de sécurité physique ni une validation des performances sur Raspberry Pi : calibration, essais réels et traitement des risques résiduels restent les conditions du passage à l'usage matériel.
