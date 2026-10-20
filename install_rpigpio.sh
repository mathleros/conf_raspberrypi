#!/usr/bin/env bash
#
# Installation du module Python RPi.GPIO pour Raspberry Pi.
#
# Usage :
#   sudo ./install_rpigpio.sh
#
# Ce module est requis pour piloter les GPIO du Raspberry Pi 5
# depuis un script Python (ex. voiture Smart Car 2WD, L298N, LEDs, etc.).

set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Ce script doit être exécuté avec sudo :"
    echo "    sudo ./install_rpigpio.sh"
    exit 1
fi

model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)
if [[ "${model}" != Raspberry* ]]; then
    echo "Erreur : ce script ne fonctionne que sur un Raspberry Pi."
    exit 1
fi

echo "Raspberry Pi détecté : ${model}"

echo "── Installation des dépendances système ──"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-pip python3-dev build-essential

echo "── Installation du module RPi.GPIO ──"
python3 -m pip install --upgrade pip setuptools wheel
if python3 - <<'PY'
import RPi.GPIO as GPIO
print(f"RPi.GPIO déjà présent : {GPIO.VERSION}")
PY
then
    echo "  RPi.GPIO est déjà installé."
else
    echo "  Installation du paquet Python RPi.GPIO…"
    python3 -m pip install --break-system-packages RPi.GPIO
fi

echo "── Vérification ──"
python3 - <<'PY'
import RPi.GPIO as GPIO
print(f"Vérification OK : RPi.GPIO {GPIO.VERSION}")
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()
PY

echo ""
echo "Installation terminée."
echo "  Exemples :"
echo "    uv run smart-car forward --duration 1"
echo "    uv run smart-car left --duration 0.5"
