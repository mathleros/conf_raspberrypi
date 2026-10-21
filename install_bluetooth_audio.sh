#!/usr/bin/env bash
#
# Installation d'un casque Bluetooth pour l'input audio / microphone.
# Adapté au Jabra Evolve 75 et à d'autres casques Bluetooth compatibles HSP/HFP.
#
# Usage :
#   sudo ./install_bluetooth_audio.sh
#
# Après installation :
#   ./scripts/connect_jabra_bt.sh scan
#   ./scripts/connect_jabra_bt.sh 08:C8:C2:38:FB:A0
#   uv run voice-assistant --once --input-device bluetooth

set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Ce script doit être exécuté avec sudo :"
    echo "    sudo ./install_bluetooth_audio.sh"
    exit 1
fi

model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)
if [[ "${model}" != Raspberry* ]]; then
    echo "Erreur : ce script ne fonctionne que sur un Raspberry Pi."
    exit 1
fi

echo "Raspberry Pi détecté : ${model}"

echo "── Installation des dépendances Bluetooth et audio ──"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    bluez \
    bluez-tools \
    pulseaudio \
    pulseaudio-utils \
    alsa-utils \
    pavucontrol


echo "── Activation des services Bluetooth ──"
if ! systemctl is-enabled bluetooth >/dev/null 2>&1; then
    systemctl enable bluetooth
fi
systemctl restart bluetooth

# Déblocage des radios Bluetooth si elles sont en mode rfkill
rfkill unblock bluetooth || true

# Démarrage de PulseAudio en mode système pour les périphériques BT
# Ce point est utile pour exposer les sources audio bluetooth à alsa/pulse.
mkdir -p /etc/pulse
if [[ ! -f /etc/pulse/client.conf ]]; then
    cat > /etc/pulse/client.conf <<'EOF'
# client.conf

auto-connect-localhost = no
EOF
fi

# Création d'un petit helper utile pour le diagnostic
cat > /usr/local/bin/bluetooth-audio-check <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if command -v pactl >/dev/null 2>&1; then
    echo "== Sources audio =="
    pactl list short sources || true
    echo
    echo "== Sinks audio =="
    pactl list short sinks || true
else
    echo "pactl non disponible. Vérifie avec : arecord -L"
    arecord -L || true
fi
EOF
chmod +x /usr/local/bin/bluetooth-audio-check

echo "── Vérification de l'installation ──"
if command -v bluetoothctl >/dev/null 2>&1; then
    echo "bluez installé : OK"
fi
if command -v pactl >/dev/null 2>&1; then
    echo "pulseaudio installé : OK"
fi


echo ""
echo "Installation terminée."
echo "" 
echo "Étapes suivantes :"
echo "  1. sudo reboot"
echo "  2. ./scripts/connect_jabra_bt.sh scan"
echo "  3. ./scripts/connect_jabra_bt.sh <MAC_ADDRESS>"
echo "  4. pactl list short sources"
echo "  5. uv run voice-assistant --once --input-device bluetooth"
echo ""
echo "Si le casque est visible mais le micro ne marche pas :"
echo "  - vérifie que le casque est en mode audio / micro (HSP/HFP)"
echo "  - vérifie les profils Bluetooth avec bluetoothctl info <MAC>"
echo "  - définis la source par défaut : pactl set-default-source <nom_source_bluez>"
