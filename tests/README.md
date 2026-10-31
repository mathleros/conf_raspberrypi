# Tests du projet

Ce dossier contient deux catégories de tests distinctes :

- `tests/unit/` : tests de logique pure, sans dépendance au matériel Raspberry Pi.
- `tests/hardware/` : scripts de validation physique sur le matériel réel (GPIO, caméra, audio, LEDs, capteurs).

## Règles de conception

- Les tests de logique métier doivent être entièrement simulés avec des objets factices.
- Les scripts d’intégration hardware restent dans `tests/hardware/` et ne doivent pas être confondus avec les tests unitaires.
- Les tests unitaires doivent rester portables entre Raspberry Pi et macOS/CI.
- La convention de nommage est cohérente :
  - `test_*.py` pour les tests unitaires
  - `test_hardware_*.py` pour les tests sur matériel réel

## Structure

- `tests/unit/` : tests de logique métier
- `tests/hardware/test_hardware_gpio.py` : validation des sorties GPIO
- `tests/hardware/test_hardware_led.py` : validation des LEDs ReSpeaker
- `tests/hardware/test_hardware_micro.py` : validation audio / micros
- `tests/hardware/test_hardware_distance.py` : validation du capteur ultrason

## Exemple de lancement

```bash
uv run pytest -q tests/unit
```

Pour les scripts hardware, lancer directement les fichiers Python depuis `tests/hardware/` sur le Raspberry Pi concerné.

## Suivi humain : sélection strictement isolée

Pour le socle protégé et les replays humains, utiliser uniquement les commandes
isolées du [protocole du lot A](../docs/test-campaign/lot-a-campagne-strictement-isolee.md),
jamais pytest globalement. Les tests de raccordement forcent les rendez-vous
concurrents avec événements et verrous réentrants bornés, libèrent les attentes
dans `finally` et joignent les threads sans les abandonner en daemon.
Les sorties du moteur factice sont observées indépendamment du journal injecté
en panne. Les résultats et contre-exemples sont consignés dans le
[rapport SH-09](../specs/backlog/08_lot_a_rapport_sh09.md#12-audit-des-cas-limites-du-raccordement-protégé-2026-10-31).
Ces tests ne raccordent aucun fournisseur humain réel.

L'outillage SH-03 possède des tests de logique sur doubles inclus dans cette
sélection et une vérification OpenCV native distincte sur points synthétiques.
Voir le [guide de calibration et relevé](../docs/test-campaign/sh03-calibration-releve.md)
pour les commandes bornées ; les campagnes live n'appartiennent pas aux tests
logiciels et exigent leur propre autorisation.

### Frontière trame → observation — replay synthétique

`test_human_perception.py` éprouve aussi
`validate_marker_observation(frame, observation, *, context, now)` et
`HumanMarkerAcquisition.observe_frame(frame, observation, *, now)`.
La capture appartient à la trame ; la publication du résultat peut être
postérieure à la publication de la trame, sans rajeunir la capture.
Les types/coordonnées incohérents lèvent une erreur explicite ; l'entrée
d'acquisition efface les confirmations avant de la propager. Les dispositions
négatives typées traversent les règles d'acquisition existantes avec leur motif.
Le chemin historique `observe` reste disponible, mais ne prouve pas la
provenance d'une trame ; un statut non typé y est maintenant refusé explicitement.
Producteurs, pixels, géométrie et calibration restent exclusivement fictifs.
Le harnais isolé ci-dessus est la seule voie de validation de cette frontière ;
voir les résultats, contre-exemples et limites du
[rapport, section 13](../specs/backlog/08_lot_a_rapport_sh09.md#13-frontière-logicielle-trame--observation-2026-10-31).

### Raccordement SH-04 source/fournisseur → cycle

Sélection ciblée, sous les mêmes gardes avant imports et collecte :

```bash
.venv/bin/python -I -S tests/isolated/run_lot_a.py --human-perception
```

Cette sélection ne collecte que `test_human_perception.py` et
`test_human_follow_runtime.py`. Elle peut aussi utiliser `--stdlib` ;
elle ne se combine pas avec `--legacy-stdlib`. La campagne de régression
reste constituée des trois commandes du protocole, sans pytest global.

Le raccordement lie à la session un `HumanPerceptionFrameSource` et un
`HumanPerceptionProvider` injectés. La source fournit un instantané atomique,
sans attendre une capture nouvelle ; indisponibilité = exception typée avec
motif, jamais `None` assimilé à une absence de marqueur. Les tests couvrent
les statuts négatifs, flux figé/interrompu/renouvelé, génération retirée,
contexte obsolète, échéances et préemption concurrente, panne du journal,
nettoyage sans fermeture de la source partagée. Aucun adaptateur caméra réel
n'est installé ; aucun paramètre optique ou temporel de production qualifié
n'est fourni par ces doubles. Voir le
[rapport, section 16](../specs/backlog/08_lot_a_rapport_sh09.md#16-raccordement-sh-04-sourcefournisseur--cycle-sur-doubles-2026-10-31).

### Garde-fous SH-05

```bash
.venv/bin/python -I -S tests/isolated/run_lot_a.py --sh05
```

Cette sélection ne collecte que `test_human_safety.py`, également inclus dans
les deux campagnes complètes contrôlées. `--stdlib` est disponible ; `--sh05`
ne se combine ni avec `--human-perception` ni avec `--legacy-stdlib`.
Après la ciblée, exécuter les trois campagnes du protocole, pas pytest global.

Le nouveau banc sépare sortie, lecteur P5, preuve, inhibition et journal.
L'oracle lit les sorties effectivement enregistrées par le double de sortie,
jamais une décision ou un verdict du journal. Conditions et enveloppes de
mouvement sont explicitement fictives ; aucune valeur PWM ne devient une
mesure au sol. Les cas couvrent préconditions isolées et en cours de mouvement,
frontières numériques/temps, événements simultanés, stop avant lecture,
demandes/résultats obsolètes, défauts des ports, propagation et reçus terminaux.
L'indisponibilité d'une sortie/observation interdit de conclure à une absence
de sortie sur la seule base du journal.

Voir le [rapport SH-05](../specs/backlog/08_lot_a_rapport_sh09.md#18-sh-05--complément-logiciel-et-campagne-isolée-2026-10-31)
et les [blocages physiques](../docs/test-campaign/sh05-blocages-physiques.md).
