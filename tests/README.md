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

Pour le socle protégé et les replays humains, utiliser uniquement les trois
commandes du [protocole du lot A](../docs/test-campaign/lot-a-campagne-strictement-isolee.md),
jamais pytest globalement. Les tests de raccordement forcent les rendez-vous
concurrents avec événements et verrous réentrants bornés, libèrent les attentes
dans `finally` et joignent les threads sans les abandonner en daemon.
Les sorties du moteur factice sont observées indépendamment du journal injecté
en panne. Les résultats et contre-exemples sont consignés dans le
[rapport SH-09](../specs/backlog/08_lot_a_rapport_sh09.md#12-audit-des-cas-limites-du-raccordement-protégé-2026-10-31).
Ces tests ne raccordent aucun fournisseur humain réel.
