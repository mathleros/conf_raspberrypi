# Pré-run checklist (Mac -> Raspberry Pi)

## A. Préparation code (Mac)
- [ ] `uv sync --project .` exécuté
- [ ] Tests unitaires verts (`pytest`)
- [ ] Script mission disponible (`scripts/test/run_mission_mac.sh`)
- [ ] Calibration chargée (`config/runtime_calibration.toml`)
- [ ] Vérification fallback LLM (serveur coupé puis relancé)

## B. Préparation runtime local (Mac)
- [ ] `run_llm_runtime_mac.sh` fonctionne
- [ ] Traces JSONL générées (`target/logs/`)
- [ ] Replay lisible (`replay_runtime_trace_mac.sh`)
- [ ] Scénarios standards exécutés (report markdown généré)

## C. Préparation hardware (Pi)
- [ ] Batterie chargée
- [ ] GND commun Pi/L298N vérifié
- [ ] Câblage moteurs (IN1..IN4, ENA/ENB) contrôlé
- [ ] Caméra fixée et focus ok
- [ ] Capteur distance connecté et lisible
- [ ] Zone de test sécurisée

## D. Gate Go/No-Go
- [ ] Arrêt d'urgence validé
- [ ] Obstacle prioritaire validé
- [ ] Timeout mission validé
- [ ] Logs exploitables validés
