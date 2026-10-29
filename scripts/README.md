# Scripts d'installation

Ce dossier contient les scripts d'installation et de validation du projet `irobot`.

## Structure du dossier

- `scripts/install/` : scripts système et de configuration (GPIO, Bluetooth, LLM, audio, etc.)
- `scripts/test/` : scripts de validation locale, de runtime, de démonstration ou de test fonctionnel sans matériel réel

## Vue d'ensemble

### Installation

- `install/install_rpigpio.sh` : installation des dépendances GPIO et du module `gpiozero`
- `install/install_respeaker.sh` : installation et configuration du HAT ReSpeaker (optionnel)
- `install/install_llm.sh` : installation du modèle local LLM + Vosk + `llama.cpp`
- `install/install_llm_mac_portable.sh` : installation portable du LLM sur macOS sans Homebrew
- `install/install_bluetooth_audio.sh` : installation du support audio Bluetooth pour un casque Jabra / microphone Bluetooth
- `install/connect_jabra_bt.sh` : appairage / connexion du casque Jabra Bluetooth

### Tests / validation locale

- `test/run_llm_runtime_mac.sh` : démarre le serveur local LLM puis exécute le runtime sur Mac, sans microphone
- `test/check_llm_latency.py` : vérifie la connectivité locale (TCP + API `/v1/models`) et la réponse `/v1/chat/completions` dans les délais configurés
- `test/replay_runtime_trace_mac.sh` : rejoue une trace JSONL générée par le runtime et affiche un résumé lisible
- `test/run_runtime_standard_scenarios_mac.sh` : exécute cinq scénarios standards Mac et produit un rapport markdown avec traces ; le cas balle jaune (recherche, approche à 1 m, suivi 300 s) réutilise `SimWorld(FakeRobot)` avec perception et horloge simulées, sans LLM pour ce cas
- `test/run_mission_mac.sh` : prototype de commande unique mission (avec option `--replay`)

## Installation recommandée

### 1. Installer les dépendances Python du projet

```bash
cd ~/Dev/conf_raspberrypi
uv venv --system-site-packages
uv sync --project .
```

### 2. Installer le support Bluetooth audio (recommandé pour le casque Jabra)

```bash
cd ~/Dev/conf_raspberrypi
sudo ./scripts/install/install_bluetooth_audio.sh
```

### 3. Appairer le casque Jabra

```bash
cd ~/Dev/conf_raspberrypi
./scripts/install/connect_jabra_bt.sh scan
./scripts/install/connect_jabra_bt.sh 08:C8:C2:38:FB:A0
```

### 4. Vérifier que le casque est bien connecté

```bash
bluetoothctl
info 08:C8:C2:38:FB:A0
```

Tu dois voir :
- `Paired: yes`
- `Connected: yes`

### 5. Lancer le test microphone Bluetooth

```bash
uv run voice-assistant --once --input-device bluetooth
```

## Installation optionnelle du ReSpeaker

Si tu souhaites garder le HAT ReSpeaker, exécute :

```bash
cd ~/Dev/conf_raspberrypi
sudo ./scripts/install/install_respeaker.sh
sudo reboot
```

Puis tu peux tester :

```bash
aplay -l
arecord -l
uv run voice-assistant --once --input-device wm8960
```

## Installation du LLM local sur macOS (portable, sans Homebrew)

```bash
cd ~/Dev/conf_raspberrypi
bash scripts/install/install_llm_mac_portable.sh
```

Cette étape installe :
- `llama.cpp`
- `llama-server`
- le modèle local GGUF dans `target/models/`
- le support de test du runtime sans microphone

## Validation locale sur Mac

Le point d’entrée unique est :

```bash
cd ~/Dev/conf_raspberrypi
bash scripts/test/run_llm_runtime_mac.sh
```

Optionnellement, avec une instruction précise :

```bash
bash scripts/test/run_llm_runtime_mac.sh --text "va vers la balle rouge"
```

La taille du contexte est configurable (4096 tokens par défaut), et le serveur peut être arrêté avec :

```bash
bash scripts/test/run_llm_runtime_mac.sh --ctx-size 8192 --text "va vers la balle rouge"
bash scripts/test/run_llm_runtime_mac.sh --stop
```

Le résultat contient un champ `trace_path` pointant vers un fichier JSONL dans `target/logs/`.
Tu peux ensuite rejouer la trace :

```bash
bash scripts/test/replay_runtime_trace_mac.sh target/logs/runtime_trace_YYYYMMDDTHHMMSSZ.jsonl
```

## Variables et commandes utiles

```bash
pactl list short sources
bluetoothctl paired-devices
bluetoothctl info <MAC>
arecord -L
```

## Conseils

- Privilégie le casque Bluetooth si tu manques de place sur le robot.
- Le ReSpeaker reste utile pour un montage fixe / prototype.
- Le projet est conçu pour fonctionner sans HAT, avec un casque Bluetooth compatible.
- Sur macOS Intel, la version portable sans Homebrew est le chemin de référence.
