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

## Lot A : campagne strictement isolée

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

Voir le [rapport SH-09 du lot A](../specs/backlog/08_lot_a_rapport_sh09.md) pour
la référence, les oracles, résultats, exclusions et limites. Le suivi humain
moteur réel demeure refusé ; aucune qualification Pi/audio/physique.
