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
