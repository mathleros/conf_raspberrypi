#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 [scan|<MAC_ADDRESS>]"
  echo "Exemples:"
  echo "  $0 scan"
  echo "  $0 00:11:22:33:44:55"
  exit 1
fi

CMD="${1:-}"

if ! command -v bluetoothctl >/dev/null 2>&1; then
  echo "Erreur: bluetoothctl n'est pas installé."
  echo "Installez le paquet bluez sur le Raspberry Pi : sudo apt install -y bluez"
  exit 1
fi

if [[ "$CMD" == "scan" ]]; then
  echo "[0/3] Scan Bluetooth du Jabra / des périphériques visibles"
  sudo bluetoothctl <<'EOF'
scan on
sleep 10
scan off
devices
quit
EOF
  exit 0
fi

MAC="$CMD"

# Nettoyage d'une ancienne liaison si elle existe
if bluetoothctl info "$MAC" >/dev/null 2>&1; then
  echo "Une paire existante a été détectée pour $MAC. Suppression de l'ancienne liaison..."
  bluetoothctl <<EOF
remove $MAC
quit
EOF
fi

# Réactivation du service Bluetooth
if ! systemctl is-active --quiet bluetooth; then
  echo "Le service Bluetooth n'est pas actif. Redémarrage en cours..."
  sudo systemctl restart bluetooth || true
  sleep 2
fi

sudo rfkill unblock bluetooth || true

# On s'assure que le Pi est prêt à appairer
# Le casque doit être mis en mode appairage séparément.
cat <<EOF

========================================
Étapes à faire sur le casque Jabra
========================================
1) Éteindre le casque.
2) Le rallumer.
3) Mettre le casque en mode appairage :
   - sur la plupart des Jabra, maintenir le bouton Call / Multi-function pendant quelques secondes.
4) Si le casque est déjà connecté à un téléphone, le déconnecter avant.
5) Quand le casque clignote en mode appairage, revenez dans ce terminal.
========================================
EOF

sleep 2

echo "[1/3] Activation du Bluetooth et du mode appairage"
bluetoothctl <<EOF
power on
agent on
default-agent
pairable on
discoverable on
EOF

echo "[2/3] Appairage du casque $MAC"
bluetoothctl <<EOF
scan on
sleep 8
pair $MAC
trust $MAC
connect $MAC
quit
EOF

echo "[3/3] Vérification du périphérique"
bluetoothctl info "$MAC" || true

echo ""
echo "Vérifiez maintenant que vous avez bien :"
echo "  - Paired: yes"
echo "  - Connected: yes"
echo ""

echo "Vérification des sources audio disponibles :"
if command -v pactl >/dev/null 2>&1; then
  pactl list short sources || true
else
  echo "pactl non disponible. Vérifie avec: arecord -L"
  arecord -L || true
fi

echo ""
echo "Teste le micro avec :"
echo "  arecord -D default -f S16_LE -r 16000 -c 1 /tmp/jabra_test.wav"
echo "  aplay /tmp/jabra_test.wav"
echo ""
echo "Puis, dans le projet :"
echo "  uv run voice-assistant --once --input-device bluetooth"
