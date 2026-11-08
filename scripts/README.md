# Scripts d'installation

Ce dossier contient les scripts d'installation et de validation du projet `irobot`.

## Structure du dossier

- `scripts/install/` : scripts système et de configuration (GPIO, Bluetooth, LLM, audio, etc.)
- `scripts/scenarios/` : scripts de validation locale, de runtime, de démonstration ou de test fonctionnel sans matériel réel

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

### Détection de visages (Pi et Mac)

Aucun installateur supplémentaire n'est nécessaire : `opencv-python`, déclaré
dans [pyproject.toml](../pyproject.toml), fournit YuNet et CLAHE. Le modèle
[face_detection_yunet_2023mar.onnx](../assets/vision/face_detection_yunet_2023mar.onnx)
et sa [licence MIT](../assets/vision/face_detection_yunet_LICENSE.txt) sont livrés dans
le dépôt : conserver ces deux fichiers lors d'une copie vers le Pi.

`install_llm.sh` synchronise déjà les dépendances Python. Le script
`install_llm_mac_portable.sh` ne gère que le LLM ; sur Mac, exécuter aussi
`uv sync --project .` comme à l'étape 1. Il n'est pas nécessaire de recompiler
llama.cpp ou de retélécharger le modèle GGUF pour activer les visages.

Depuis la racine du projet, vérifier le chargement du modèle et une inférence
sans caméra, sans visage réel et sans moteur :

```bash
uv run python - <<'PY'
import numpy as np
from irobot.common.config.settings import load_runtime_settings
from irobot.common.hardware.camera.detector import FaceDetector

detector = FaceDetector(load_runtime_settings())
assert detector.detect(np.zeros((640, 480, 3), dtype=np.uint8)) is None
print("YuNet : chargement et inference OK")
PY
```

Le chemin `face_model_path` de la section `[camera]` de
[runtime_settings.toml](../src/irobot/common/config/runtime_settings.toml) est relatif à ce
fichier TOML, ou absolu. Une absence du modèle ou une erreur OpenCV est signalée,
sans téléchargement automatique ni repli silencieux. Le contrôle ci-dessus
ne qualifie ni la caméra Picamera2 sur le Pi, ni la précision des distances,
ni le suivi moteur ; ces essais matériels restent nécessaires.

Sur le Pi avec un affichage X11, lancer le diagnostic commun :

```bash
uv run vision-detect-live
```

Il affiche simultanément l'ID ArUco 1, le visage sélectionné et les balles
rouge/jaune, avec leurs distances estimées, sans piloter les moteurs ni enregistrer
d'images. Ajouter `--preview-only` pour afficher le flux sans détection ni
annotation. `q` ou Ctrl+C quitte l'outil. Après mise à jour du dépôt, exécuter
`uv sync --project .` pour installer la commande `vision-detect-live`.

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
uv run robot --once --input-device bluetooth
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
uv run robot --once --input-device wm8960
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
bash scripts/scenarios/run_llm_runtime_mac.sh
```

Optionnellement, avec une instruction précise :

```bash
bash scripts/scenarios/run_llm_runtime_mac.sh --text "va vers la balle rouge"
```

La taille du contexte est configurable (4096 tokens par défaut), et le serveur peut être arrêté avec :

```bash
bash scripts/scenarios/run_llm_runtime_mac.sh --ctx-size 8192 --text "va vers la balle rouge"
bash scripts/scenarios/run_llm_runtime_mac.sh --stop
```

Le résultat contient un champ `trace_path` pointant vers un fichier JSONL dans `target/logs/`.
Tu peux ensuite rejouer la trace :

```bash
bash scripts/scenarios/replay_runtime_trace_mac.sh target/logs/runtime_trace_YYYYMMDDTHHMMSSZ.jsonl
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
