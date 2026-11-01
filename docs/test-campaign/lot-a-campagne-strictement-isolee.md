# Lot A : campagne strictement isolée

Ne pas lancer globalement la suite pour ce lot : l'intégration LLM existante
peut rechercher des modèles et démarrer un serveur. Depuis `conf_raspberrypi` :

```bash
.venv/bin/python -I -S tests/isolated/run_lot_a.py --stdlib
.venv/bin/python -I -S tests/isolated/run_lot_a.py
.venv/bin/python -I -S tests/isolated/run_lot_a.py --legacy-stdlib
```

Le lanceur pose les gardes avant imports/collecte, désactive l'initialisation
`site` et les plugins automatiques, injecte les ports complémentaires factices
et ne sélectionne que les fichiers contrôlés. Il charge pytest déjà installé
localement sans exécuter les `.pth` ; dépendance absente = blocage, sans installation.
Les nombres de temps/protection du nouveau socle sont exclusivement fictifs.
Une tentative interdite ou un thread résiduel invalide la campagne.

La borne murale du harnais interrompt explicitement la campagne avec un code
non nul ; son exception ne peut pas être absorbée par les traitements métier
`except Exception`. Une campagne interrompue ou un observateur indisponible
reste inconclusif, jamais une preuve d'absence de sortie. Les tests injectent
la borne dans un vrai skill à horloge/perception/moteur factices, sans attendre
son échéance murale.

Les cas du lot vérifient aussi le refus intégral des demandes humaines et des
cibles de suivi non prises en charge, avant LLM factice, filtrage ou exécution
partielle : aucun repli d'une cible inconnue vers `yellow`. L'omission de
couleur d'une demande objet historique prise en charge reste compatible.
Les préconditions humaines sont énumérées dans un contrat d'exigences fixe,
indépendant des champs du type de production.

La sélection isolée inclut aussi `tests/unit/test_human_perception.py` :
contrat typé, instantané immuable de l'identité persistante au contexte de
mission, acquisition et décodeur ArUco à partir d'observations/doubles
synthétiques seulement. La cible SH-04 (200 ms) est une valeur de test
explicite, non une mesure qualifiée ; aucun accès caméra ou matériel n'est
invoqué. Un smoke test natif OpenCV distinct utilise également une image
synthétique uniquement pour vérifier que l'API locale se construit ; il ne
qualifie pas la perception optique.

`tests/unit/test_human_lifecycle.py` vérifie les transitions d'acquisition,
maintien, suspension/reprise et échéance avec une horloge et des résultats
synthétiques. La machine ne commande aucun mouvement et n'est pas raccordée
au runtime mission ; elle ne qualifie ni annonces, protections ni arrêt réel.

`tests/unit/test_human_follow_runtime.py` vérifie le raccordement structuré du
cycle humain au runtime protégé : réservation immobile en acquisition,
activation après annonce, refus L2 des commandes non nulles hors phase active,
suspension/reprise locale avec nouveau contexte et même échéance, invalidation
des annonces obsolètes et non-régression du runtime commun balle/humain/balle
sur doubles uniquement. Aucun fournisseur de mouvement humain réel n'est exposé.
Le replay concurrent force maintenant une tentative de reprise du verrou
d'émission par l'évaluateur pendant que P1 le détient, puis vérifie sa
libération avant l'attente du verrou d'évaluation. Les attentes sont bornées,
libérées dans `finally` et les threads joints. Les cas complémentaires couvrent
les sept phases contre stop/P1/P3/P6, les frontières exactes de l'échéance,
les résultats obsolètes et les pannes de journal pendant préparation,
activation/reprise et franchissement d'échéance. Un journal bloqué ne retarde
pas la remise du zéro par le stop local.

`tests/unit/test_marker_diagnostic.py` vérifie le contrat de présentation du
diagnostic ArUco sans caméra. La commande `marker-detect-live` ouvre la caméra
réelle et son affichage. Une campagne statique avec marqueur a été autorisée
séparément ; ne pas la lancer pendant la validation isolée ni avant
synchronisation explicite du code vers le Pi.

Après synchronisation du code sur le Pi, invocation depuis la racine du dépôt
sans réinstaller de dépendance :

```bash
PYTHONPATH=src .venv/bin/python -m irobot.interfaces.marker_diagnostic
```

Cette commande ouvre la caméra 0 uniquement si son modèle est rapporté comme
OV5647, détecte le seul couple configuré dans le diagnostic
`DICT_4X4_50`/ID `1`, affiche les coins en pixels et ne sauvegarde pas d'image.
Elle exige une campagne réelle autorisée séparément ; `camera-live` déjà
autorisé ne couvre pas cette détection.

Le diagnostic estime la **distance directe entre l'objectif et le centre du
marqueur** via `solvePnP` sur les quatre coins du carré de 8 cm : son inclinaison
est prise en compte, contrairement à une estimation par largeur apparente.
La capture est fixée à 640×480 avant rotation (480×640 après rotation).
La focale provisoire reste 600 px, le centre optique est supposé au centre de
l'image et la distorsion est supposée nulle : ce n'est pas une calibration
de l'objectif et la précision aux bords n'est pas garantie. L'affichage vidéo
est actualisé à chaque trame (`~` indique une estimation) ; la console reste
limitée aux changements de statut. Une pose inexploitable affiche une distance
indisponible, sans repli sur la largeur. Le pipeline runtime partage désormais
ce calcul de pose avec le diagnostic ; une pose inexploitable y est journalisée
et ne fournit aucune détection.
Les tests de pose utilisent uniquement des projections synthétiques ; ils ne
valident pas les erreurs physiques rapportées sur le Pi.

Voir le [rapport SH-09 du lot A](../../specs/backlog/08_lot_a_rapport_sh09.md)
pour la référence, les oracles, résultats, exclusions et limites. Le suivi
humain moteur réel demeure refusé ; aucune qualification Pi/audio/physique.

Dernière reproduction locale après audit des cas limites (2026-10-31) :

| Campagne | Résultat |
|---|---|
| `tests/isolated/run_lot_a.py --stdlib` | 246 tests réussis |
| `tests/isolated/run_lot_a.py` | 296 réussis, 7 désélectionnés, 112 sous-tests réussis |
| `tests/isolated/run_lot_a.py --legacy-stdlib` | 4 contrats réussis |

Trois processus : zéro accès interdit, zéro thread résiduel et trois sondes
synthétiques refusées chacun. Les séries intermédiaires en échec et les cinq
défauts corrigés sont conservés au
[rapport, section 12](../../specs/backlog/08_lot_a_rapport_sh09.md#12-audit-des-cas-limites-du-raccordement-protégé-2026-10-31).
Les confirmations de l'acquisition sont toutes fraîches à sa décision ; leur
historique est borné à trois captures. Une acquisition déjà établie conserve
sa continuité sur les nouvelles trames valides ; une invalidation remet les
confirmations à zéro. Aucun budget ni réglage de production ajouté.

### Résultat communiqué depuis le Pi — 2026-10-31

L’utilisateur rapporte avoir exécuté depuis le dépôt sur le Pi :

```bash
.venv/bin/python -I -S tests/isolated/run_lot_a.py
```

Sortie rapportée : **284 réussis, 7 désélectionnés, 61 sous-tests réussis en
1,10 s** ; `forbidden accesses=0`, `residual threads=0` et trois sondes de
politique synthétiques rejetées, sans opération sur une ressource.

Ce résultat est rapporté par l’utilisateur, non reproduit indépendamment ici.
Il confirme uniquement l’exécution de cette sélection isolée dans
l’environnement utilisé ; il ne valide ni matériel réel, ni caméra/audio,
ni protection physique, ni propulsion ou suivi d’une personne.

### Frontière logicielle trame → observation — 2026-10-31

Nouvelle série locale, distincte des résultats historiques ci-dessus, exécutée
avec les mêmes trois commandes `-I -S`, sans élargir la sélection :

| Campagne | Résultat effectivement reproduit |
|---|---|
| `tests/isolated/run_lot_a.py --stdlib` | 263 tests réussis ; 16,256 s |
| `tests/isolated/run_lot_a.py` | 313 réussis, 7 désélectionnés, 269 sous-tests réussis ; 27,73 s |
| `tests/isolated/run_lot_a.py --legacy-stdlib` | 4 contrats réussis ; 0,300 s |

Chaque processus : code 0, zéro accès interdit, zéro thread résiduel et trois
sondes synthétiques rejetées. Aucun nouveau thread n'est créé par le replay
de perception ; les contrôles de raccordement concurrents existants restent
sélectionnés. Les temps sont ceux du harnais local, pas des latences qualifiées.

Les producteurs définis uniquement dans `test_human_perception.py` éprouvent
la provenance source/génération/trame/capture/mission/contexte, l'ordre
`capture <= publication trame <= publication résultat <= maintenant`,
les types malformés/non finis, retards, répétitions et flux anciens/changés.
Les résultats traversent ensuite l'acquisition existante : trois confirmations
distinctes et fraîches, bornes incluses, invalidation et continuité acquise.
Ni pixels opaques inspectés, ni distance/calibration/qualité inférée.
Erreurs de frontière propagées après invalidation des confirmations ;
statuts négatifs typés conservés, sans fallback ni confusion absence/défaut.

Le contre-exemple initial (247 tests, un échec et deux erreurs), la série
intermédiaire corrigée et les limites sont conservés au
[rapport, section 13](../../specs/backlog/08_lot_a_rapport_sh09.md#13-frontière-logicielle-trame--observation-2026-10-31).
Le résultat Pi reste rapporté, non reproduit indépendamment. Aucun fournisseur
concret ni raccordement caméra/runtime, aucun Go terrain ou clôture globale.

### Replay synthétique vers le cycle humain — 2026-10-31

Dernière campagne locale après raccordement de `observe_frame` au
`HumanFollowRuntime` et aux annonces structurées :

| Campagne | Résultat |
|---|---|
| `--stdlib` | 265 tests réussis |
| sélection contrôlée | 315 réussis, 7 désélectionnés, 272 sous-tests réussis |
| `--legacy-stdlib` | 4 contrats réussis |

Chaque processus : code 0, zéro accès interdit, zéro thread résiduel, trois
sondes synthétiques refusées. Tests exclusivement sur doubles : parcours trame
→ acquisition → annonce ; résultats en vol invalidés après suspension, stop et
échéance. Aucun moteur non nul, caméra, audio réel, Pi, GPIO ou personne.
`follow_person` reste refusé par le parcours linguistique de production.

Voir le [rapport SH-09, section 14](../../specs/backlog/08_lot_a_rapport_sh09.md#14-replay-synthétique-frontière--cycle-et-annonces-2026-10-31).
Cette campagne logicielle ne qualifie ni fournisseur réel, perception optique,
calibration, protection matérielle ni autorisation de mouvement.

### Outillage SH-03 — calibration et relevé

`test_marker_calibration.py` est inclus dans les sélections stdlib et pytest :
confirmations avant acquisition, validation des paramètres/calibrations,
décompte de captures distinctes, conservation des statuts négatifs,
absence de métriques temporelles qualifiées et lecture des traces hors ligne.
Ni OpenCV natif ni Picamera2 ne sont importés par ces tests.

`test_marker_calibration_opencv.py` reste exclu du lot A ; son invocation
distincte et exclusivement synthétique est documentée dans le
[guide de calibration/relevé SH-03](sh03-calibration-releve.md).
Ce guide décrit aussi les commandes live, interdites dans le harnais isolé
et soumises à autorisation de campagne distincte. Aucun réglage de production
ni qualification SH-03 n'est produit par l'outillage.

### Raccordement SH-04 — sélection ciblée et campagne finale

Avant les trois commandes de régression du début de ce protocole :

```bash
.venv/bin/python -I -S tests/isolated/run_lot_a.py --human-perception
```

Seuls les deux fichiers humains de perception/raccordement sont collectés,
avec les mêmes gardes, borne murale et contrôles de threads. Aucun plugin,
matériel, modèle ou serveur additionnel. L'option `--stdlib` peut compléter
cette sélection ciblée ; `--legacy-stdlib` ne peut pas la compléter.

Dernière reproduction SH-04 locale (2026-10-31), distincte des séries
historiques et du bloc d'outillage SH-03 ci-dessus :

| Sélection | Résultat |
|---|---|
| ciblée `--human-perception` | 104 réussis, 290 sous-tests réussis ; 13,72 s |
| campagne `--stdlib` | 295 tests réussis ; 19,544 s |
| campagne pytest contrôlée | 345 réussis, 7 désélectionnés, 308 sous-tests réussis ; 27,99 s |
| contrats `--legacy-stdlib` | 4 réussis ; 0,406 s |

Les quatre processus : code 0, zéro accès interdit, zéro thread résiduel,
trois sondes synthétiques refusées chacun. Les temps sont ceux des harnais
locaux, pas des latences de perception qualifiées. La campagne complète
inclut aussi les tests d'outillage SH-03 ajoutés parallèlement ; elle n'exécute
pas sa vérification OpenCV native ni ses commandes live.

Source/fournisseur uniquement injectés sur doubles : trames opaques,
provenance et horodatages conservés, indisponibilité distincte de l'absence,
reprise explicite avec trois confirmations nouvelles, même échéance,
générations retirées et captures précédant le nouveau contexte rejetées.
Arrêt/échéance préemptent les résultats en vol ; nettoyage sans fermer la
source partagée, y compris sous panne du journal. Le parcours humain réel
reste refusé, sans caméra réelle ni mouvement physique. Voir le
[rapport SH-09, section 16](../../specs/backlog/08_lot_a_rapport_sh09.md#16-raccordement-sh-04-sourcefournisseur--cycle-sur-doubles-2026-10-31).

### SH-04 — budgets configurables provisoires et revalidation

Après autorisation explicite des défauts non qualifiés, puis confirmation du
périmètre `safe-config`, le raccordement existant lit les budgets de
`[human_follow]` dans
[runtime_calibration.toml](../../config/runtime_calibration.toml) :
`max_age_seconds = 0.2`, `announcement_timeout_seconds = 2.0`.
Ils ne qualifient pas la fraîcheur/latence physique et ne lèvent aucun refus
humain réel. Les ports restent injectés, sans producteur optique matériel.

Nouvelle reproduction locale du 2026-10-31 :

| Sélection | Résultat |
|---|---|
| ciblée `--human-perception` | 112 réussis, 343 sous-tests ; 15,28 s |
| campagne `--stdlib` | 303 réussis ; 17,250 s |
| campagne pytest contrôlée | 353 réussis, 7 désélectionnés, 361 sous-tests ; 24,73 s |
| contrats `--legacy-stdlib` | 4 réussis ; 0,249 s |

Les quatre processus finaux : code 0, zéro accès interdit, zéro thread résiduel,
trois sondes synthétiques refusées chacun. Mêmes sélections et gardes, aucune
installation. Les tests supplémentaires contrôlent le chargement/validation,
la priorité des surcharges, la trace des budgets réellement employés,
l'expiration exacte de l'annonce et le maintien des budgets à la reprise.
Les cas existants de flux interrompu/renouvelé, péremption, ambiguïté, contexte
obsolète, stop/échéance et nettoyage sont rejoués.
La première ciblée a échoué sur trois attendus des nouveaux tests ; corrections
et limites sont consignées au
[rapport SH-09, section 17](../../specs/backlog/08_lot_a_rapport_sh09.md#17-sh-04--budgets-configurables-provisoires-et-revalidation-2026-10-31).

### SH-05 — admission, émission et propagation

Commencer par la sélection ciblée, puis les trois commandes complètes du
début de ce protocole :

```bash
.venv/bin/python -I -S tests/isolated/run_lot_a.py --sh05
```

La ciblée sélectionne uniquement `tests/unit/test_human_safety.py`.
Elle peut utiliser `--stdlib`, mais ne se combine ni avec
`--human-perception` ni avec `--legacy-stdlib`. Gardes, borne murale, imports
interdits et vérification des threads inchangés. Le fichier SH-05 est ajouté
aux deux sélections complètes ; aucun fichier matériel/LLM ajouté.

Reproduction locale finale du 2026-10-31 :

| Sélection | Résultat |
|---|---|
| ciblée `--sh05` | 35 réussis, 146 sous-tests ; 1,19 s |
| campagne `--stdlib` | 338 réussis ; 12,871 s |
| campagne pytest contrôlée | 388 réussis, 7 désélectionnés, 507 sous-tests ; 21,30 s |
| contrats `--legacy-stdlib` | 4 réussis ; 0,375 s |

Chaque processus final : code 0, zéro accès interdit, zéro thread résiduel et
trois sondes synthétiques refusées. Temps locaux de harnais, non latences
qualifiées ; les campagnes complètes ont été lancées dans des processus
distincts en parallèle, pas dans un environnement de mesure physique isolé.

Le banc SH-05 possède des doubles distincts de sortie/P5/preuve/inhibition/
journal et des oracles indépendants des traces de décision. Préconditions
inconnues, limites de mouvement, arrêt avant lecture, défauts simultanés,
invalidations, échéance inchangée, reçus d'interruption et arrêts sans succès
de substitution sont testés. Les contrats communs balle/primitives/stop,
perception, lifecycle, entrées texte/intention/voix factice et réessais sont
rejoués. Le stop protégé retourne désormais `stopped` et termine le plan ;
le stop non protégé et les règles de mouvement balle sont conservés.

Contre-exemples, empreintes et preuves :
[rapport SH-09, section 18](../../specs/backlog/08_lot_a_rapport_sh09.md#18-sh-05--complément-logiciel-et-campagne-isolée-2026-10-31).
Qualifications non exécutées :
[blocages physiques SH-05](sh05-blocages-physiques.md).
**Aucun moteur activé, aucun Go humain et aucune clôture globale SH-05/SH-09.**
