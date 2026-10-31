# SH-03 — calibration candidate et relevé automatique

Outil : [marker_calibration.py](../../src/irobot/interfaces/marker_calibration.py).
Invocation depuis la racine du dépôt, sans installation ni modification de
`runtime_calibration.toml`. Aucun moteur, GPIO, audio ou runtime de mission
n'est importé. Aucune image n'est enregistrée : seuls coins, métadonnées,
paramètres et résultats numériques sont conservés.

**Générer l'outil n'autorise pas son exécution matérielle.** Chaque campagne
live exige un accord explicite couvrant ouverture caméra, damier/marqueur,
conditions et durée. Les trois options de confirmation ci-dessous sont des
déclarations opérateur, pas une protection physique ni une autorisation en soi.
Moteurs physiquement déconnectés et impossibles à alimenter, robot immobile,
zone sans personne pendant les captures, montage stable et X11 disponible.
Caméra 0 refusée si son modèle n'est pas rapporté OV5647.

## 1. Préparer les références

- Relever le hash exact sur le Pi (`git rev-parse HEAD`) et les modifications
  locales ; reporter un identifiant de révision reproductible, pas « HEAD ».
- Choisir un identifiant de montage accompagné des hauteurs, inclinaisons et
  déports mesurés. Le réutiliser exactement ; toute modification demande une
  nouvelle calibration/revalidation.
- Pour les intrinsèques : damier plan rigide et mat, carrés mesurés en cm.
  `--columns` et `--rows` désignent les **coins intérieurs**, pas les cases.
  Par exemple 9×6 coins demandent 10×7 cases ; `--square-cm 2` n'est correct
  que si le côté imprimé mesuré est réellement 2 cm.
  Le [damier SVG prêt à imprimer](../../config/damier_calibration_9x6_20mm.svg)
  est au format A4 paysage, avec cases de 20 mm et une référence de 100 mm.
  Imprimer en taille réelle / 100 %, sans ajustement ni en-têtes/pieds de page,
  puis vérifier les dimensions imprimées avant utilisation.
- Pour ArUco : `DICT_4X4_50`/ID `1`, carré imprimé mesuré hors marge, déclaré
  à 8 cm dans le dossier. Le damier et le marqueur sont deux cibles distinctes.

Le pipeline est fixé pour cet outil à 640×480, format Picamera2 `BGR888`
(octets RGB), sans transformation matérielle intentionnelle, puis rotation
horaire de 90° : image traitée **480×640**. Le format est explicitement fixé
pour éviter une conversion couleur dépendant du preview par défaut.
Les matrices produites s'appliquent à cette image tournée, sans changement
de taille, recadrage ou montage. La configuration effective est journalisée.

## 2. Collecter les coins du damier

Après autorisation de cette campagne, remplacer les valeurs d'exemple par les
références et dimensions réellement relevées :

```bash
PYTHONPATH=src .venv/bin/python -m irobot.interfaces.marker_calibration calibrate \
  --columns 9 --rows 6 --square-cm 2 \
  --samples 20 --interval-s 1 --duration-s 120 \
  --revision HASH_EXACT_PI --mounting "MONTAGE_MESURE_A" \
  --output damier-01.jsonl --calibration-output intrinseques-01.json \
  --authorized-camera --motors-isolated --zone-empty
```

Chaque capture est journalisée, y compris damier absent. Les vues sélectionnées
ont un `SensorTimestamp` nouveau et croissant, sont espacées par l'intervalle
choisi et diffèrent de la dernière sélection de plus de 2 pixels sur au moins
une coordonnée. **Ce filtre anti-répétition ne démontre pas la diversité** :
prévoir distances, inclinaisons et positions variées couvrant centre et bords,
sans flou, avec tous les coins visibles. Les seuils de collecte et le minimum
de 12 vues sont des choix d'outillage, pas des réglages de production ni des
critères de qualification optique.

**Ne pas entrer dans la zone pour déplacer le damier caméra ouverte.**
Deux possibilités :

- Le support est repositionnable depuis l'extérieur de la zone, sans personne
  présente dans celle-ci : collecte multi-vues autorisée dans ce périmètre.
- Sinon, prépositionner le damier caméra fermée, sortir de la zone, lancer une
  capture, puis quitter par `q` avant chaque repositionnement. Répéter avec
  des noms de fichiers distincts, puis combiner les traces hors ligne.

`q`, Ctrl+C ou échéance avant le nombre demandé donnent un code non nul :
le relevé partiel reste dans le JSONL ; le fichier de calibration réservé
reste vide et **n'est pas une calibration utilisable**.
Une pose fixe peut ne fournir qu'une vue sélectionnée : c'est attendu.
La borne de durée est contrôlée entre captures ; elle ne garantit pas qu'un
pilote bloqué dans `capture_request()` réponde dans ce délai.

## 3. Calculer hors ligne

Cette commande **n'ouvre aucune caméra**, ne requiert pas de DISPLAY ni
d'autorisation matérielle et combine les vues sélectionnées de traces
compatibles, même arrêtées volontairement :

```bash
PYTHONPATH=src .venv/bin/python -m irobot.interfaces.marker_calibration solve \
  --columns 9 --rows 6 --square-cm 2 \
  --revision HASH_EXACT_PI --mounting "MONTAGE_MESURE_A" \
  --traces damier-01.jsonl damier-02.jsonl damier-03.jsonl \
  --output intrinseques-finales.json
```

Fournir autant de traces que nécessaire pour **au moins 12 vues sélectionnées
et réellement diverses**. Les chemins répétés et copies identiques sont
refusés, ainsi que les traces échouées, tronquées, d'un autre montage,
révision, pipeline ou damier. Un cinquième des vues (au moins deux) est réservé
pour estimer les erreurs de reprojection hors ajustement des intrinsèques.

La sortie contient matrice `fx/fy/cx/cy`, cinq coefficients OpenCV
`k1/k2/p1/p2/k3`, RMS d'ajustement, erreurs de chaque vue d'entraînement et de
validation, références et empreintes des traces pour le calcul hors ligne.
Il s'agit d'une **calibration candidate** : aucune borne de qualité n'est
inventée, aucun verdict SH-03 ne découle du seul succès de `calibrateCamera`.
Des vues peu diverses peuvent donner une calibration médiocre ; examiner
les erreurs, le champ couvert et la précision sur des références indépendantes.

## 4. Relever une condition ArUco

Nouvelle campagne live, à autoriser dans son périmètre précis ; utiliser des
fichiers distincts par condition nominale ou négative :

```bash
PYTHONPATH=src .venv/bin/python -m irobot.interfaces.marker_calibration record \
  --calibration intrinseques-finales.json --marker-cm 8 \
  --condition "cible inerte; distance/hauteur/angles/decalage/eclairage mesures" \
  --revision HASH_EXACT_PI --mounting "MONTAGE_MESURE_A" \
  --frames 100 --duration-s 30 --output aruco-condition-01.jsonl \
  --authorized-camera --motors-isolated --zone-empty
```

Pour une comparaison de distance optique, ajouter ensemble
`--reference-optical-cm DISTANCE_MESUREE` et
`--reference-uncertainty-cm INCERTITUDE_MESUREE` (valeurs positives).
La référence est la distance **centre optique → centre du marqueur**,
indépendante de la caméra ; pas le dégagement robot–porteur.

Chaque trame comporte timestamp capteur brut, temps monotones de retour et
de résultat, exposition/gain, coins, statut absent/ambigu/rejet/défaut ou
détection, et candidats de pose du carré par IPPE. Les poses derrière la
caméra/non finies ne sont pas exploitées ; les solutions restantes sont
toutes conservées. Deux solutions = `pose_status: ambiguous` :
**aucun choix arbitraire par plus faible erreur de reprojection**.
Distance euclidienne optique, profondeur, reprojection et erreur optique
signée par candidat sont des diagnostics, pas une distance de production.
`robot_clearance_cm` reste `null`.

Le résumé compte captures nouvelles, répétées, hors ordre et timestamps
absents ; taux de **détection**, séries sans détection et débit de captures
nouvelles. Une répétition n'ajoute jamais un échantillon. Timestamp absent
ou régressif : exclusion explicite du décompte, sans capture inventée.
Une session interrompue/insuffisante retourne un code non nul et conserve
son résumé ; les erreurs sont explicites, la caméra est arrêtée et fermée
lors de la sortie normale ou exceptionnelle du processus.

**La p95 mesurée est retour de capture → résultat**, incluant copie/conversion/
détection/pose, mais excluant attente et délai capteur/pipeline.
`capture_to_result_p95_ms` reste `null` : le lien entre `SensorTimestamp` et
l'horloge locale doit être vérifié avant de prétendre mesurer fraîcheur ou
latence complète. Cette p95 n'est donc pas le critère SH-03 de 150 ms.

## 5. Qualification restant à réaliser

Appliquer [les critères SH-03](../../specs/backlog/07_suivi_humain_marqueur_backlog.md)
à chaque condition nominale : ≥100 captures nouvelles, observations
**acceptées** ≥95 %, erreur de **dégagement** ≤20 cm pour ≥95 % des acceptées.
Caractériser pertes, biais, maxima, cas négatifs, débit cible ≥10 observations
nouvelles/s et p95 capture→observation ≤150 ms sur Pi, puis sous charge SH-10.

Cet outil fournit intrinsèques candidates, traces et poses ambiguës explicites,
mais pas la transformation robot–porteur, la résolution qualifiée des poses
ambiguës, les seuils de qualité ou une validation du temps capteur.
Ces éléments, les mesures indépendantes/incertitudes, le support porté et les
essais de marche lente restent requis pour fermer SH-03. Aucun fichier produit
n'est chargé par le runtime humain. `sh03_qualified` reste toujours `false`.
Ni cet outil, ni une campagne réussie ne lèvent SH-02/SH-11 ou le refus humain
de production.

## Vérification logicielle

Tests de logique sur doubles inclus dans les trois commandes de la
[campagne strictement isolée](lot-a-campagne-strictement-isolee.md).
Test OpenCV natif distinct, uniquement sur points synthétiques et caméra
factice, sans fenêtre ni périphérique :

```bash
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest \
  --noconftest -p no:cacheprovider -q tests/unit/test_marker_calibration_opencv.py
```
