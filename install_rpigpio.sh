#!/usr/bin/env bash
#
# Installation du module Python gpiozero pour Raspberry Pi.
#
# Usage :
#   sudo ./install_rpigpio.sh
#
# gpiozero est le pilote GPIO recommandé sur Raspberry Pi 5 / Debian 13.
# Il remplace RPi.GPIO, qui n'est pas fiable sur cette plateforme.

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
apt-get install -y python3-pip python3-dev build-essential python3-gpiozero

echo "── Vérification du module gpiozero ──"
python3 - <<'PY'
import gpiozero
print(f"Vérification OK : gpiozero {gpiozero.__version__}")
PY

echo ""
echo "Installation terminée."
echo "  Exemples :"
echo "    uv sync --project ."
echo "    uv run smart-car forward --duration 1"
echo "    uv run smart-car left --duration 0.5"
