# Scripts d'installation

Ce dossier contient les scripts d'installation et de configuration du projet `irobot`.

## Vue d'ensemble

- `install_rpigpio.sh` : installation des dépendances GPIO et du module `gpiozero`
- `install_respeaker.sh` : installation et configuration du HAT ReSpeaker (optionnel)
- `install_llm.sh` : installation du modèle local LLM + Vosk + `llama.cpp`
- `install_bluetooth_audio.sh` : installation du support audio Bluetooth pour un casque Jabra / microphone Bluetooth
- `connect_jabra_bt.sh` : appairage / connexion du casque Jabra Bluetooth

## ReSpeaker : optionnel

Le ReSpeaker n'est pas obligatoire pour le fonctionnement du projet.

Le projet supporte désormais deux modes d'entrée audio :
- audio Bluetooth (casque Jabra, micro Bluetooth, etc.)
- audio local via ReSpeaker (optionnel, si tu veux conserver le HAT)

Le ReSpeaker est donc considéré comme une option matérielle facultative.

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
sudo ./scripts/install_bluetooth_audio.sh
```

### 3. Appairer le casque Jabra

```bash
cd ~/Dev/conf_raspberrypi
./scripts/connect_jabra_bt.sh scan
./scripts/connect_jabra_bt.sh 08:C8:C2:38:FB:A0
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
sudo ./scripts/install_respeaker.sh
sudo reboot
```

Puis tu peux tester :

```bash
aplay -l
arecord -l
uv run voice-assistant --once --input-device wm8960
```

## Installation du LLM local

```bash
cd ~/Dev/conf_raspberrypi
sudo ./scripts/install_llm.sh
```

Cette étape installe :
- `llama.cpp`
- `llama-server`
- le modèle local de langue
- le modèle Vosk FR pour la reconnaissance vocale

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
