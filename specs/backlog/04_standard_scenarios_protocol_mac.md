# Protocole Mac — Scénarios standards (préparation avant Pi)

## Objectif
Valider la logique runtime/LLM/orchestration avant exécution physique.

## Script
- `scripts/test/run_runtime_standard_scenarios_mac.sh`

## Scénarios inclus
1. Avance 20 cm
2. Rotation droite
3. Search and approach (avec mock objet)
4. Contournement obstacle

## Procédure
1. Lancer le script.
2. Ouvrir le report markdown généré dans `target/logs/scenario_runs/`.
3. Vérifier pour chaque scénario :
   - statut non `rejected`
   - trace présente (`TRACE_PATH`)
4. Rejouer au moins une trace avec `replay_runtime_trace_mac.sh`.

## Critères de validation
- 4/4 scénarios exécutés
- aucun crash runtime
- traces exploitables présentes
